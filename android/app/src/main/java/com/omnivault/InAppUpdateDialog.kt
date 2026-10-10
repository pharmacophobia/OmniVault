package com.omnivault

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.SystemUpdate
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun InAppUpdateDialog(
    appName: String,
    updateInfo: AppUpdateInfo,
    onDismiss: () -> Unit,
    onInstallUpdate: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.SystemUpdate, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(8.dp))
                Text(
                    if (updateInfo.updateAvailable) "New Update Available!" else "$appName is Up to Date",
                    fontWeight = FontWeight.Bold,
                    fontSize = 18.sp
                )
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (updateInfo.updateAvailable) {
                    Text(
                        "Version v${updateInfo.latestVersion} is now available (Current: v${updateInfo.currentVersion}).",
                        fontWeight = FontWeight.Medium,
                        color = Color(0xFFA6E3A1)
                    )
                    if (updateInfo.releaseNotes.isNotEmpty()) {
                        Text("What's New:", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = Color(0xFF313244),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                updateInfo.releaseNotes,
                                modifier = Modifier.padding(10.dp),
                                fontSize = 12.sp,
                                color = Color(0xFFCDD6F4)
                            )
                        }
                    }
                } else {
                    Text("You are running the latest version (v${updateInfo.currentVersion}). No updates needed.")
                }
            }
        },
        confirmButton = {
            if (updateInfo.updateAvailable) {
                Button(
                    onClick = onInstallUpdate,
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFA6E3A1))
                ) {
                    Text("Download & Install", color = Color(0xFF11111B), fontWeight = FontWeight.Bold)
                }
            } else {
                TextButton(onClick = onDismiss) { Text("OK") }
            }
        },
        dismissButton = {
            if (updateInfo.updateAvailable) {
                TextButton(onClick = onDismiss) { Text("Later") }
            }
        }
    )
}
