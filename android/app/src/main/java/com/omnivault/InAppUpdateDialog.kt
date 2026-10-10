package com.omnivault

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.OpenInBrowser
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
    downloadProgress: Int, // -1: not started, 0..100: in progress/finished
    isDownloading: Boolean,
    onDismiss: () -> Unit,
    onStartDownload: () -> Unit,
    onOpenInBrowser: () -> Unit
) {
    AlertDialog(
        onDismissRequest = {
            if (!isDownloading) onDismiss()
        },
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
                        "Version v${updateInfo.latestVersion} is available (Current: v${updateInfo.currentVersion}).",
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

                    if (isDownloading) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            if (downloadProgress >= 100) "Download complete! Opening package installer..." else "Downloading update: $downloadProgress%",
                            fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Bold
                        )
                        if (downloadProgress in 0..100) {
                            LinearProgressIndicator(
                                progress = { downloadProgress / 100f },
                                modifier = Modifier.fillMaxWidth().height(8.dp),
                                color = MaterialTheme.colorScheme.secondary
                            )
                        } else {
                            LinearProgressIndicator(modifier = Modifier.fillMaxWidth().height(8.dp))
                        }
                    }
                } else {
                    Text("You are running the latest version (v${updateInfo.currentVersion}). You can still force-reinstall if desired.")
                }
            }
        },
        confirmButton = {
            if (!isDownloading) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = onStartDownload,
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFA6E3A1))
                    ) {
                        Icon(Icons.Default.Download, contentDescription = null, tint = Color(0xFF11111B))
                        Spacer(Modifier.width(4.dp))
                        Text(
                            if (updateInfo.updateAvailable) "Download & Install" else "Re-download",
                            color = Color(0xFF11111B),
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
        },
        dismissButton = {
            if (!isDownloading) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = onOpenInBrowser) {
                        Icon(Icons.Default.OpenInBrowser, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Browser Link")
                    }
                    TextButton(onClick = onDismiss) { Text("Close") }
                }
            }
        }
    )
}
