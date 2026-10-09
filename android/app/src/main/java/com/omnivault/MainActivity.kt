package com.omnivault

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import kotlinx.coroutines.launch
import org.json.JSONObject

class MainActivity : FragmentActivity() {

    private lateinit var repository: VaultRepository
    private lateinit var networkClient: NetworkClient

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        repository = VaultRepository(this)
        networkClient = NetworkClient(this)

        setContent {
            OmniVaultTheme {
                OmniVaultApp(
                    repository = repository,
                    networkClient = networkClient,
                    onRequestBiometrics = { onSuccess, onError ->
                        promptBiometrics(onSuccess, onError)
                    },
                    onCopyToClipboard = { label, text ->
                        copyToClipboard(label, text)
                    }
                )
            }
        }
    }

    private fun promptBiometrics(onSuccess: () -> Unit, onError: (String) -> Unit) {
        val biometricManager = BiometricManager.from(this)
        val canAuthenticate = biometricManager.canAuthenticate(
            BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL
        )

        if (canAuthenticate != BiometricManager.BIOMETRIC_SUCCESS) {
            onError("Biometrics not enrolled or unavailable on this device. Please use Master Password.")
            return
        }

        val executor = ContextCompat.getMainExecutor(this)
        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle("Unlock OmniVault")
            .setSubtitle("Authenticate using your fingerprint, face, or device PIN")
            .setAllowedAuthenticators(
                BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL
            )
            .build()

        val biometricPrompt = BiometricPrompt(this, executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    super.onAuthenticationSucceeded(result)
                    onSuccess()
                }

                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    super.onAuthenticationError(errorCode, errString)
                    onError(errString.toString())
                }

                override fun onAuthenticationFailed() {
                    super.onAuthenticationFailed()
                    onError("Biometric authentication failed. Try again.")
                }
            })

        biometricPrompt.authenticate(promptInfo)
    }

    private fun copyToClipboard(label: String, text: String) {
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = ClipData.newPlainText(label, text)
        clipboard.setPrimaryClip(clip)
        Toast.makeText(this, "Copied $label to clipboard", Toast.LENGTH_SHORT).show()
    }
}

@Composable
fun OmniVaultTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            background = Color(0xFF181825),
            surface = Color(0xFF1E1E2E),
            primary = Color(0xFF89B4FA),
            secondary = Color(0xFFA6E3A1),
            error = Color(0xFFF38BA8),
            onBackground = Color(0xFFCDD6F4),
            onSurface = Color(0xFFCDD6F4)
        ),
        content = content
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OmniVaultApp(
    repository: VaultRepository,
    networkClient: NetworkClient,
    onRequestBiometrics: (onSuccess: () -> Unit, onError: (String) -> Unit) -> Unit,
    onCopyToClipboard: (label: String, text: String) -> Unit
) {
    var isUnlocked by remember { mutableStateOf(repository.isUnlocked) }
    var masterPasswordInput by remember { mutableStateOf("") }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var searchQuery by remember { mutableStateOf("") }

    // Dialog states
    var showAddDialog by remember { mutableStateOf(false) }
    var showGenDialog by remember { mutableStateOf(false) }
    var showSyncDialog by remember { mutableStateOf(false) }
    var editingEntry by remember { mutableStateOf<VaultEntry?>(null) }
    var desktopHost by remember { mutableStateOf("10.0.12.97") } // default subnet IP
    var isProcessingVision by remember { mutableStateOf(false) }

    val coroutineScope = rememberCoroutineScope()

    // Screenshot picker launcher
    val photoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            isProcessingVision = true
            errorMessage = "Processing screenshot through local Ollama vision model..."
            coroutineScope.launch {
                val extracted = networkClient.extractFromScreenshot(desktopHost, uri)
                isProcessingVision = false
                if (extracted != null) {
                    errorMessage = null
                    editingEntry = VaultEntry(
                        id = "entry_${System.currentTimeMillis()}",
                        service = extracted.optString("service", ""),
                        account = extracted.optString("account", ""),
                        password = extracted.optString("password", "")
                    )
                    showAddDialog = true
                } else {
                    errorMessage = "Failed to extract credentials. Ensure desktop sync server is running."
                }
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Lock, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.width(8.dp))
                        Text("OmniVault", fontWeight = FontWeight.Bold)
                    }
                },
                actions = {
                    if (isUnlocked) {
                        IconButton(onClick = { showGenDialog = true }) {
                            Icon(Icons.Default.Casino, contentDescription = "Password Generator")
                        }
                        IconButton(onClick = { showSyncDialog = true }) {
                            Icon(Icons.Default.Sync, contentDescription = "Sync Desktop")
                        }
                        IconButton(onClick = {
                            repository.lock()
                            isUnlocked = false
                        }) {
                            Icon(Icons.Default.Lock, contentDescription = "Lock Vault", tint = MaterialTheme.colorScheme.error)
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface)
            )
        },
        floatingActionButton = {
            if (isUnlocked) {
                Column(horizontalAlignment = Alignment.End) {
                    FloatingActionButton(
                        onClick = { photoPickerLauncher.launch("image/*") },
                        containerColor = Color(0xFFFAB387),
                        contentColor = Color(0xFF11111B),
                        modifier = Modifier.padding(bottom = 12.dp)
                    ) {
                        Icon(Icons.Default.DocumentScanner, contentDescription = "Import Screenshot")
                    }
                    FloatingActionButton(
                        onClick = {
                            editingEntry = null
                            showAddDialog = true
                        },
                        containerColor = MaterialTheme.colorScheme.secondary,
                        contentColor = Color(0xFF11111B)
                    ) {
                        Icon(Icons.Default.Add, contentDescription = "Add Credential")
                    }
                }
            }
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(MaterialTheme.colorScheme.background)
        ) {
            if (!isUnlocked) {
                // Unlock / Biometrics Screen
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Icon(
                        Icons.Default.Shield,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(72.dp)
                    )
                    Spacer(Modifier.height(16.dp))
                    Text(
                        "Vault is Locked",
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onBackground
                    )
                    Spacer(Modifier.height(8.dp))
                    Text(
                        if (repository.hasVault()) "Authenticate with Biometrics or Master Password" else "Create your Master Password to get started",
                        fontSize = 14.sp,
                        color = Color(0xFFA6ADC8)
                    )

                    Spacer(Modifier.height(24.dp))

                    if (repository.hasVault()) {
                        Button(
                            onClick = {
                                onRequestBiometrics(
                                    {
                                        // On biometric success, if active master key cached or empty
                                        if (repository.activeMasterPassword != null) {
                                            isUnlocked = true
                                        } else {
                                            errorMessage = "Please enter Master Password once to decrypt cryptographic keys."
                                        }
                                    },
                                    { err -> errorMessage = err }
                                )
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(Icons.Default.Fingerprint, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text("Unlock with Biometrics", fontWeight = FontWeight.Bold)
                        }

                        Spacer(Modifier.height(16.dp))
                        Text("— OR —", color = Color(0xFF6C7086), fontSize = 12.sp)
                        Spacer(Modifier.height(16.dp))
                    }

                    OutlinedTextField(
                        value = masterPasswordInput,
                        onValueChange = { masterPasswordInput = it },
                        label = { Text("Master Password") },
                        visualTransformation = PasswordVisualTransformation(),
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )

                    Spacer(Modifier.height(16.dp))

                    Button(
                        onClick = {
                            if (repository.hasVault()) {
                                if (repository.unlock(masterPasswordInput)) {
                                    isUnlocked = true
                                    errorMessage = null
                                } else {
                                    errorMessage = "Invalid Master Password"
                                }
                            } else {
                                if (masterPasswordInput.length >= 6) {
                                    repository.createVault(masterPasswordInput)
                                    isUnlocked = true
                                    errorMessage = null
                                } else {
                                    errorMessage = "Password must be at least 6 characters"
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(if (repository.hasVault()) "Unlock Vault" else "Create New Vault", fontWeight = FontWeight.Bold)
                    }

                    if (errorMessage != null) {
                        Spacer(Modifier.height(16.dp))
                        Text(errorMessage!!, color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
                    }
                }
            } else {
                // Unlocked Vault View
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(16.dp)
                ) {
                    OutlinedTextField(
                        value = searchQuery,
                        onValueChange = { searchQuery = it },
                        leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                        placeholder = { Text("Search services, usernames...") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp)
                    )

                    Spacer(Modifier.height(12.dp))

                    val filtered = repository.entries.filter {
                        it.service.contains(searchQuery, ignoreCase = true) ||
                        it.account.contains(searchQuery, ignoreCase = true) ||
                        it.notes.contains(searchQuery, ignoreCase = true)
                    }

                    if (filtered.isEmpty()) {
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text("No credentials found. Tap + to add or 📷 to scan screenshot.", color = Color(0xFFA6ADC8))
                        }
                    } else {
                        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            items(filtered) { entry ->
                                CredentialCard(
                                    entry = entry,
                                    onCopyAccount = { onCopyToClipboard("Username", entry.account) },
                                    onCopyPassword = { onCopyToClipboard("Password", entry.password) },
                                    onEdit = {
                                        editingEntry = entry
                                        showAddDialog = true
                                    },
                                    onDelete = {
                                        repository.deleteEntry(entry.id)
                                    }
                                )
                            }
                        }
                    }
                }
            }

            // Dialogs
            if (showAddDialog) {
                AddEditEntryDialog(
                    initialEntry = editingEntry,
                    onDismiss = { showAddDialog = false },
                    onSave = { updated ->
                        repository.addOrUpdateEntry(updated)
                        showAddDialog = false
                    }
                )
            }

            if (showGenDialog) {
                PasswordGeneratorDialog(
                    onDismiss = { showGenDialog = false },
                    onCopy = { pw -> onCopyToClipboard("Generated Password", pw) }
                )
            }

            if (showSyncDialog) {
                SyncDesktopDialog(
                    host = desktopHost,
                    onHostChange = { desktopHost = it },
                    networkClient = networkClient,
                    repository = repository,
                    onDismiss = { showSyncDialog = false }
                )
            }
        }
    }
}

@Composable
fun CredentialCard(
    entry: VaultEntry,
    onCopyAccount: () -> Unit,
    onCopyPassword: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    var passwordVisible by remember { mutableStateOf(false) }

    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    entry.service,
                    fontWeight = FontWeight.Bold,
                    fontSize = 17.sp,
                    color = MaterialTheme.colorScheme.primary
                )
                Row {
                    IconButton(onClick = onEdit) {
                        Icon(Icons.Default.Edit, contentDescription = "Edit", modifier = Modifier.size(20.dp))
                    }
                    IconButton(onClick = onDelete) {
                        Icon(Icons.Default.Delete, contentDescription = "Delete", tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(20.dp))
                    }
                }
            }

            Spacer(Modifier.height(4.dp))

            // Account row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(entry.account, fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
                Button(
                    onClick = onCopyAccount,
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF313244))
                ) {
                    Text("Copy Acc", fontSize = 11.sp, color = Color(0xFFCDD6F4))
                }
            }

            Spacer(Modifier.height(6.dp))

            // Password row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    if (passwordVisible) entry.password else "••••••••••••",
                    fontFamily = FontFamily.Monospace,
                    fontSize = 14.sp,
                    color = if (passwordVisible) Color(0xFFA6E3A1) else Color(0xFFA6ADC8)
                )
                Row {
                    IconButton(onClick = { passwordVisible = !passwordVisible }) {
                        Icon(
                            if (passwordVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                            contentDescription = "Toggle visibility",
                            modifier = Modifier.size(18.dp)
                        )
                    }
                    Button(
                        onClick = onCopyPassword,
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                    ) {
                        Text("Copy Pass", fontSize = 11.sp, color = Color(0xFF11111B), fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}

@Composable
fun AddEditEntryDialog(
    initialEntry: VaultEntry?,
    onDismiss: () -> Unit,
    onSave: (VaultEntry) -> Unit
) {
    var service by remember { mutableStateOf(initialEntry?.service ?: "") }
    var account by remember { mutableStateOf(initialEntry?.account ?: "") }
    var password by remember { mutableStateOf(initialEntry?.password ?: "") }
    var notes by remember { mutableStateOf(initialEntry?.notes ?: "") }
    var url by remember { mutableStateOf(initialEntry?.url ?: "") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (initialEntry != null) "Edit Credential" else "Add Credential") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = service, onValueChange = { service = it }, label = { Text("Service Name") }, singleLine = true)
                OutlinedTextField(value = account, onValueChange = { account = it }, label = { Text("Account / Email") }, singleLine = true)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = { Text("Password") },
                        modifier = Modifier.weight(1f)
                    )
                    Spacer(Modifier.width(4.dp))
                    Button(
                        onClick = { password = PasswordGenerator.generate(18) },
                        contentPadding = PaddingValues(4.dp)
                    ) {
                        Text("🎲", fontSize = 16.sp)
                    }
                }
                OutlinedTextField(value = url, onValueChange = { url = it }, label = { Text("URL (optional)") }, singleLine = true)
                OutlinedTextField(value = notes, onValueChange = { notes = it }, label = { Text("Notes (optional)") }, maxLines = 3)
            }
        },
        confirmButton = {
            Button(onClick = {
                val id = initialEntry?.id ?: "entry_${System.currentTimeMillis()}"
                onSave(VaultEntry(id, service, account, password, notes, url))
            }) {
                Text("Save")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        }
    )
}

@Composable
fun PasswordGeneratorDialog(onDismiss: () -> Unit, onCopy: (String) -> Unit) {
    var length by remember { mutableStateOf(18) }
    var password by remember { mutableStateOf(PasswordGenerator.generate(18)) }
    val strength = PasswordGenerator.calculateStrength(password)

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("🎲 Password Generator") },
        text = {
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(password, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 18.sp, color = Color(0xFFA6E3A1))
                Text("Strength: ${strength.label}", color = MaterialTheme.colorScheme.primary, fontSize = 13.sp)
                Slider(value = length.toFloat(), onValueChange = { length = it.toInt(); password = PasswordGenerator.generate(length) }, valueRange = 8f..32f)
                Text("Length: $length", fontSize = 12.sp)
            }
        },
        confirmButton = {
            Button(onClick = {
                onCopy(password)
                onDismiss()
            }) {
                Text("Copy & Use")
            }
        },
        dismissButton = {
            Button(onClick = { password = PasswordGenerator.generate(length) }) {
                Text("Re-roll")
            }
        }
    )
}

@Composable
fun SyncDesktopDialog(
    host: String,
    onHostChange: (String) -> Unit,
    networkClient: NetworkClient,
    repository: VaultRepository,
    onDismiss: () -> Unit
) {
    var statusText by remember { mutableStateOf("Enter Desktop Wi-Fi IP (Port 8765)") }
    val scope = rememberCoroutineScope()

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("🔄 Sync with Desktop Vault") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = host,
                    onValueChange = onHostChange,
                    label = { Text("Desktop IP Address") },
                    singleLine = true
                )
                Text(statusText, fontSize = 12.sp, color = Color(0xFFA6ADC8))
            }
        },
        confirmButton = {
            Button(onClick = {
                scope.launch {
                    statusText = "Pulling encrypted vault from Desktop..."
                    val env = networkClient.pullVault(host)
                    if (env != null) {
                        val saved = repository.saveRemoteEnvelope(env, repository.activeMasterPassword)
                        statusText = if (saved) "Synced vault successfully!" else "Vault received, but could not decrypt with active password."
                    } else {
                        statusText = "Sync failed. Check connection."
                    }
                }
            }) {
                Text("Pull from Desktop")
            }
        },
        dismissButton = {
            Button(onClick = {
                scope.launch {
                    val env = repository.getEncryptedEnvelope()
                    if (env != null) {
                        statusText = "Pushing vault to Desktop..."
                        val (ok, msg) = networkClient.pushVault(host, env)
                        statusText = msg
                    } else {
                        statusText = "No local vault to push."
                    }
                }
            }) {
                Text("Push to Desktop")
            }
        }
    )
}
