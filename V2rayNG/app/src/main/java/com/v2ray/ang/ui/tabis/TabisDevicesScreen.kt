package com.v2ray.ang.ui.tabis

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.v2ray.ang.R
import com.v2ray.ang.ui.tabis.theme.TabisColors
import com.v2ray.ang.ui.tabis.theme.TabisShapes
import kotlinx.coroutines.launch

@Composable
fun TabisDevicesScreen(
    isDarkTheme: Boolean,
    onNavigateToProfile: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val textColor = if (isDarkTheme) TabisColors.DarkText else TabisColors.LightText
    val textMuted = if (isDarkTheme) TabisColors.DarkTextMuted else TabisColors.LightTextMuted
    val textDim = if (isDarkTheme) TabisColors.DarkTextDim else TabisColors.LightTextDim
    val cardBg = if (isDarkTheme) TabisColors.DarkCard else TabisColors.LightCard
    val cardSubtle = if (isDarkTheme) TabisColors.DarkCardSubtle else TabisColors.LightCardSubtle
    val borderColor = if (isDarkTheme) TabisColors.DarkBorder else TabisColors.LightBorder
    val badgeBg = if (isDarkTheme) TabisColors.DarkBadgeBg else TabisColors.LightBadgeBg

    var devices by remember { mutableStateOf<List<TabisDevice>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }

    // Add device modal state
    var showAddDialog by remember { mutableStateOf(false) }
    var newDeviceName by remember { mutableStateOf("") }
    var selectedTariffPlan by remember { mutableStateOf("base") } // "base" (60) or "premium" (240)
    var isAddingDevice by remember { mutableStateOf(false) }

    // Change tariff modal state
    var deviceToChangeTariff by remember { mutableStateOf<TabisDevice?>(null) }
    var changeTariffPlan by remember { mutableStateOf("base") }
    var isChangingTariff by remember { mutableStateOf(false) }

    // Delete device modal state
    var deviceToDelete by remember { mutableStateOf<TabisDevice?>(null) }
    var isDeletingDevice by remember { mutableStateOf(false) }

    fun refreshDevices() {
        isLoading = true
        scope.launch {
            val (_, devList) = TabisSecurityManager.fetchProfileMe()
            devices = devList
            isLoading = false
        }
    }

    LaunchedEffect(Unit) {
        refreshDevices()
    }

    // --- ADD DEVICE DIALOG ---
    if (showAddDialog) {
        AlertDialog(
            onDismissRequest = { if (!isAddingDevice) showAddDialog = false },
            title = {
                Text(
                    text = stringResource(R.string.tabis_devices_add_title),
                    fontWeight = FontWeight.Bold,
                    color = textColor
                )
            },
            text = {
                Column {
                    OutlinedTextField(
                        value = newDeviceName,
                        onValueChange = { newDeviceName = it },
                        placeholder = { Text(stringResource(R.string.tabis_devices_name_hint), color = textDim) },
                        singleLine = true,
                        shape = TabisShapes.Input,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = TabisColors.AccentBlue,
                            unfocusedBorderColor = borderColor,
                            focusedTextColor = textColor,
                            unfocusedTextColor = textColor
                        ),
                        modifier = Modifier.fillMaxWidth()
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    Text(
                        text = stringResource(R.string.tabis_devices_tariff_label),
                        color = textDim,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp,
                        letterSpacing = 1.sp
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    // Base Tariff Option
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(TabisShapes.InnerCard)
                            .background(if (selectedTariffPlan == "base") TabisColors.AccentBlueBg else cardSubtle)
                            .border(
                                if (selectedTariffPlan == "base") 1.dp else 0.5.dp,
                                if (selectedTariffPlan == "base") TabisColors.AccentBlue else borderColor,
                                TabisShapes.InnerCard
                            )
                            .clickable { selectedTariffPlan = "base" }
                            .padding(14.dp)
                    ) {
                        Text(
                            text = stringResource(R.string.tabis_devices_tariff_base),
                            color = textColor,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // Premium Tariff Option
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(TabisShapes.InnerCard)
                            .background(if (selectedTariffPlan == "premium") TabisColors.AccentBlueBg else cardSubtle)
                            .border(
                                if (selectedTariffPlan == "premium") 1.dp else 0.5.dp,
                                if (selectedTariffPlan == "premium") TabisColors.AccentBlue else borderColor,
                                TabisShapes.InnerCard
                            )
                            .clickable { selectedTariffPlan = "premium" }
                            .padding(14.dp)
                    ) {
                        Text(
                            text = stringResource(R.string.tabis_devices_tariff_premium),
                            color = textColor,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        isAddingDevice = true
                        scope.launch {
                            val (success, msg) = TabisSecurityManager.addDevice(newDeviceName.trim(), selectedTariffPlan)
                            isAddingDevice = false
                            if (success) {
                                showAddDialog = false
                                newDeviceName = ""
                                refreshDevices()
                            } else {
                                Toast.makeText(context, msg.ifBlank { "Ошибка добавления устройства" }, Toast.LENGTH_SHORT).show()
                            }
                        }
                    },
                    enabled = newDeviceName.trim().isNotBlank() && !isAddingDevice,
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                ) {
                    if (isAddingDevice) {
                        CircularProgressIndicator(color = Color.White, modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                    } else {
                        Text(stringResource(R.string.tabis_dialog_ok), color = Color.White)
                    }
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { showAddDialog = false },
                    enabled = !isAddingDevice
                ) {
                    Text(stringResource(R.string.tabis_dialog_cancel), color = textDim)
                }
            },
            containerColor = cardBg,
            shape = TabisShapes.Card
        )
    }

    // --- CHANGE TARIFF DIALOG ---
    deviceToChangeTariff?.let { dev ->
        AlertDialog(
            onDismissRequest = { if (!isChangingTariff) deviceToChangeTariff = null },
            title = {
                Text(
                    text = "${stringResource(R.string.tabis_devices_change_tariff)}: ${dev.deviceName}",
                    fontWeight = FontWeight.Bold,
                    color = textColor
                )
            },
            text = {
                Column {
                    // Base Tariff Option
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(TabisShapes.InnerCard)
                            .background(if (changeTariffPlan == "base") TabisColors.AccentBlueBg else cardSubtle)
                            .border(
                                if (changeTariffPlan == "base") 1.dp else 0.5.dp,
                                if (changeTariffPlan == "base") TabisColors.AccentBlue else borderColor,
                                TabisShapes.InnerCard
                            )
                            .clickable { changeTariffPlan = "base" }
                            .padding(14.dp)
                    ) {
                        Text(
                            text = stringResource(R.string.tabis_devices_tariff_base),
                            color = textColor,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // Premium Tariff Option
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(TabisShapes.InnerCard)
                            .background(if (changeTariffPlan == "premium") TabisColors.AccentBlueBg else cardSubtle)
                            .border(
                                if (changeTariffPlan == "premium") 1.dp else 0.5.dp,
                                if (changeTariffPlan == "premium") TabisColors.AccentBlue else borderColor,
                                TabisShapes.InnerCard
                            )
                            .clickable { changeTariffPlan = "premium" }
                            .padding(14.dp)
                    ) {
                        Text(
                            text = stringResource(R.string.tabis_devices_tariff_premium),
                            color = textColor,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        isChangingTariff = true
                        scope.launch {
                            val (success, msg) = TabisSecurityManager.changeDeviceTariff(dev.id, changeTariffPlan)
                            isChangingTariff = false
                            if (success) {
                                deviceToChangeTariff = null
                                refreshDevices()
                            } else {
                                Toast.makeText(context, msg.ifBlank { "Ошибка смены тарифа" }, Toast.LENGTH_SHORT).show()
                            }
                        }
                    },
                    enabled = !isChangingTariff,
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                ) {
                    if (isChangingTariff) {
                        CircularProgressIndicator(color = Color.White, modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                    } else {
                        Text(stringResource(R.string.tabis_dialog_ok), color = Color.White)
                    }
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { deviceToChangeTariff = null },
                    enabled = !isChangingTariff
                ) {
                    Text(stringResource(R.string.tabis_dialog_cancel), color = textDim)
                }
            },
            containerColor = cardBg,
            shape = TabisShapes.Card
        )
    }

    // --- DELETE DEVICE DIALOG ---
    deviceToDelete?.let { dev ->
        AlertDialog(
            onDismissRequest = { if (!isDeletingDevice) deviceToDelete = null },
            title = {
                Text(
                    text = stringResource(R.string.tabis_devices_delete_device),
                    fontWeight = FontWeight.Bold,
                    color = TabisColors.DisconnectedRed
                )
            },
            text = {
                Text(
                    text = stringResource(R.string.tabis_devices_delete_confirm, dev.deviceName),
                    color = textMuted,
                    fontSize = 14.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        isDeletingDevice = true
                        scope.launch {
                            val (success, msg) = TabisSecurityManager.deleteDevice(dev.id)
                            isDeletingDevice = false
                            if (success) {
                                deviceToDelete = null
                                refreshDevices()
                            } else {
                                Toast.makeText(context, msg.ifBlank { "Ошибка удаления устройства" }, Toast.LENGTH_SHORT).show()
                            }
                        }
                    },
                    enabled = !isDeletingDevice,
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.DisconnectedRed)
                ) {
                    if (isDeletingDevice) {
                        CircularProgressIndicator(color = Color.White, modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                    } else {
                        Text("Удалить", color = Color.White)
                    }
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { deviceToDelete = null },
                    enabled = !isDeletingDevice
                ) {
                    Text(stringResource(R.string.tabis_dialog_cancel), color = textDim)
                }
            },
            containerColor = cardBg,
            shape = TabisShapes.Card
        )
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp)
            .padding(top = 16.dp, bottom = 104.dp)
    ) {
        // Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = stringResource(R.string.tabis_devices_title),
                    color = textColor,
                    fontWeight = FontWeight.Bold,
                    fontSize = 22.sp
                )
                Text(
                    text = "HARDWARE TUNNELS (${devices.size}/5)",
                    color = textDim,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                    letterSpacing = 1.sp
                )
            }

            Box(
                modifier = Modifier
                    .clip(TabisShapes.Badge)
                    .background(badgeBg)
                    .border(0.5.dp, borderColor, TabisShapes.Badge)
                    .clickable { refreshDevices() }
                    .padding(horizontal = 12.dp, vertical = 6.dp)
            ) {
                Text(
                    text = if (isLoading) "ОБНОВЛЕНИЕ..." else "ОБНОВИТЬ",
                    color = TabisColors.AccentBlue,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = stringResource(R.string.tabis_devices_subtitle),
            color = textMuted,
            fontSize = 13.sp,
            lineHeight = 18.sp
        )

        Spacer(modifier = Modifier.height(20.dp))

        // Device Cards List
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            devices.forEach { dev ->
                DeviceCard(
                    device = dev,
                    isDarkTheme = isDarkTheme,
                    onChangeTariff = {
                        changeTariffPlan = if (dev.tariffPlan == "premium") "premium" else "base"
                        deviceToChangeTariff = dev
                    },
                    onDelete = {
                        deviceToDelete = dev
                    }
                )
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Add Device Action
        if (devices.size < 5) {
            Button(
                onClick = {
                    newDeviceName = ""
                    selectedTariffPlan = "base"
                    showAddDialog = true
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(54.dp),
                shape = TabisShapes.Pill,
                colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
            ) {
                Text(
                    text = stringResource(R.string.tabis_devices_add_btn),
                    color = Color.White,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.SemiBold
                )
            }
        } else {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(TabisShapes.Card)
                    .background(cardBg)
                    .border(0.5.dp, borderColor, TabisShapes.Card)
                    .padding(16.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = stringResource(R.string.tabis_devices_limit_msg),
                    color = textMuted,
                    fontSize = 13.sp,
                    fontFamily = FontFamily.Monospace
                )
            }
        }
    }
}

@Composable
private fun DeviceCard(
    device: TabisDevice,
    isDarkTheme: Boolean,
    onChangeTariff: () -> Unit,
    onDelete: () -> Unit
) {
    val textColor = if (isDarkTheme) TabisColors.DarkText else TabisColors.LightText
    val textMuted = if (isDarkTheme) TabisColors.DarkTextMuted else TabisColors.LightTextMuted
    val textDim = if (isDarkTheme) TabisColors.DarkTextDim else TabisColors.LightTextDim
    val cardBg = if (isDarkTheme) TabisColors.DarkCard else TabisColors.LightCard
    val cardSubtle = if (isDarkTheme) TabisColors.DarkCardSubtle else TabisColors.LightCardSubtle
    val borderColor = if (isDarkTheme) TabisColors.DarkBorder else TabisColors.LightBorder

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(TabisShapes.Card)
            .background(cardBg)
            .border(0.5.dp, borderColor, TabisShapes.Card)
            .padding(18.dp)
    ) {
        Column {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .background(TabisColors.AccentBlueBg),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            painter = painterResource(R.drawable.ic_tabis_devices),
                            contentDescription = null,
                            tint = TabisColors.AccentBlue,
                            modifier = Modifier.size(18.dp)
                        )
                    }

                    Spacer(modifier = Modifier.width(12.dp))

                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = device.deviceName,
                                color = textColor,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold
                            )
                            if (device.isPrimary) {
                                Spacer(modifier = Modifier.width(8.dp))
                                Box(
                                    modifier = Modifier
                                        .clip(TabisShapes.Badge)
                                        .background(TabisColors.AccentBlueBg)
                                        .padding(horizontal = 6.dp, vertical = 2.dp)
                                ) {
                                    Text(
                                        text = stringResource(R.string.tabis_devices_primary_badge),
                                        color = TabisColors.AccentBlue,
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 9.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                        }

                        Text(
                            text = "${device.tariffName} (${device.monthlyCost} ₽/мес)",
                            color = textMuted,
                            fontSize = 12.sp,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                }

                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .clip(CircleShape)
                        .background(if (device.isActive) TabisColors.ConnectedGreen else TabisColors.DisconnectedRed)
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Traffic & Days remaining Info
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(TabisShapes.InnerCard)
                    .background(cardSubtle)
                    .border(0.5.dp, borderColor, TabisShapes.InnerCard)
                    .padding(horizontal = 12.dp, vertical = 10.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = stringResource(R.string.tabis_devices_traffic_label),
                            color = textDim,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 9.sp
                        )
                        Text(
                            text = "${device.trafficGb} GB",
                            color = textColor,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.SemiBold,
                            modifier = Modifier.padding(top = 1.dp)
                        )
                    }

                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            text = stringResource(R.string.tabis_devices_days_left, device.daysRemaining),
                            color = if (device.daysRemaining > 3) TabisColors.ConnectedGreen else TabisColors.DisconnectedRed,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            text = device.statusText,
                            color = textDim,
                            fontSize = 10.sp,
                            modifier = Modifier.padding(top = 1.dp)
                        )
                    }
                }
            }

            // Device Code / Token with Copy
            if (device.token.isNotBlank()) {
                Spacer(modifier = Modifier.height(10.dp))
                val context = LocalContext.current
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(TabisShapes.InnerCard)
                        .background(cardSubtle)
                        .border(0.5.dp, borderColor, TabisShapes.InnerCard)
                        .clickable {
                            val clipboard = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
                            val clip = android.content.ClipData.newPlainText("Device Code", device.token)
                            clipboard?.setPrimaryClip(clip)
                            Toast.makeText(context, context.getString(R.string.tabis_devices_code_copied), Toast.LENGTH_SHORT).show()
                        }
                        .padding(horizontal = 12.dp, vertical = 9.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = stringResource(R.string.tabis_devices_code_label),
                            color = textDim,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = device.token,
                            color = TabisColors.AccentBlue,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Icon(
                        painter = painterResource(R.drawable.ic_copy),
                        contentDescription = stringResource(R.string.tabis_devices_copy_code),
                        tint = textMuted,
                        modifier = Modifier.size(16.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Device Actions
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically
            ) {
                TextButton(onClick = onChangeTariff) {
                    Text(
                        text = stringResource(R.string.tabis_devices_change_tariff),
                        color = TabisColors.AccentBlue,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }

                if (!device.isPrimary) {
                    Spacer(modifier = Modifier.width(8.dp))
                    TextButton(onClick = onDelete) {
                        Text(
                            text = stringResource(R.string.tabis_devices_delete_device),
                            color = TabisColors.DisconnectedRed,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }
            }
        }
    }
}
