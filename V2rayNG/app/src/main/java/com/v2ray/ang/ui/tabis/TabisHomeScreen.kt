package com.v2ray.ang.ui.tabis

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.Image
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import com.v2ray.ang.AppConfig
import com.v2ray.ang.R
import com.v2ray.ang.dto.entities.ServersCache
import com.v2ray.ang.ui.main.MainAction
import com.v2ray.ang.ui.main.MainStatus
import com.v2ray.ang.ui.tabis.theme.TabisColors
import com.v2ray.ang.ui.tabis.theme.TabisShapes
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun TabisHomeScreen(
    isRunning: Boolean,
    status: MainStatus,
    displayText: String,
    selectedServer: ServersCache?,
    serversCount: Int,
    isDarkTheme: Boolean,
    onAction: (MainAction) -> Unit,
    onOpenServerPicker: () -> Unit,
    onOpenDrawer: () -> Unit,
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

    var sessionSeconds by remember { mutableIntStateOf(0) }
    LaunchedEffect(isRunning) {
        if (isRunning) {
            while (true) {
                delay(1000)
                sessionSeconds++
            }
        } else {
            sessionSeconds = 0
        }
    }

    val uptimeStr = remember(sessionSeconds) {
        val hrs = sessionSeconds / 3600
        val mins = (sessionSeconds % 3600) / 60
        val secs = sessionSeconds % 60
        String.format("%02d:%02d:%02d", hrs, mins, secs)
    }

    var showZeroBalanceDialog by remember { mutableStateOf(false) }
    var zeroBalanceMessage by remember { mutableStateOf("") }
    var showRevokedDialog by remember { mutableStateOf(false) }
    var revokedMessage by remember { mutableStateOf("") }
    var isCheckingEligibility by remember { mutableStateOf(false) }

    val userBalance = TabisSecurityManager.getUserBalance()
    val isNewUser = TabisSecurityManager.isNewUser()
    val showZeroBalanceBanner = (userBalance <= 0 || isNewUser) && !isRunning

    fun handleConnectTap() {
        if (isRunning) {
            onAction(MainAction.ToggleService)
        } else {
            isCheckingEligibility = true
            scope.launch {
                val (checkResult, msg) = TabisSecurityManager.checkConnectionEligibility()
                isCheckingEligibility = false
                when (checkResult) {
                    ConnectionStatusCheck.ALLOWED -> {
                        onAction(MainAction.ToggleService)
                    }
                    ConnectionStatusCheck.ZERO_BALANCE -> {
                        zeroBalanceMessage = msg.ifBlank {
                            context.getString(R.string.tabis_dialog_zero_balance_msg)
                        }
                        showZeroBalanceDialog = true
                    }
                    ConnectionStatusCheck.ACCESS_REVOKED,
                    ConnectionStatusCheck.DEVICE_DELETED -> {
                        revokedMessage = msg
                        showRevokedDialog = true
                    }
                }
            }
        }
    }

    if (showZeroBalanceDialog) {
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { showZeroBalanceDialog = false },
            title = {
                Text(
                    text = stringResource(R.string.tabis_dialog_zero_balance_title),
                    fontWeight = FontWeight.Bold,
                    color = textColor
                )
            },
            text = {
                Text(
                    text = zeroBalanceMessage,
                    color = textMuted,
                    fontSize = 14.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showZeroBalanceDialog = false
                        onNavigateToProfile()
                    },
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                ) {
                    Text(stringResource(R.string.tabis_dialog_zero_balance_btn), color = Color.White)
                }
            },
            dismissButton = {
                androidx.compose.material3.TextButton(
                    onClick = { showZeroBalanceDialog = false }
                ) {
                    Text(stringResource(R.string.tabis_dialog_cancel), color = textDim)
                }
            },
            containerColor = cardBg,
            shape = TabisShapes.Card
        )
    }

    if (showRevokedDialog) {
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { showRevokedDialog = false },
            title = {
                Text(
                    text = stringResource(R.string.tabis_dialog_revoked_title),
                    fontWeight = FontWeight.Bold,
                    color = textColor
                )
            },
            text = {
                Text(
                    text = revokedMessage,
                    color = textMuted,
                    fontSize = 14.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showRevokedDialog = false
                        try {
                            val intent = android.content.Intent(
                                android.content.Intent.ACTION_VIEW,
                                android.net.Uri.parse("https://t.me/atlzgamerz")
                            )
                            context.startActivity(intent)
                        } catch (_: Exception) {}
                    },
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                ) {
                    Text(stringResource(R.string.tabis_dialog_telegram_btn), color = Color.White)
                }
            },
            dismissButton = {
                androidx.compose.material3.TextButton(
                    onClick = { showRevokedDialog = false }
                ) {
                    Text(stringResource(R.string.tabis_dialog_ok), color = textDim)
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
            .padding(top = 16.dp, bottom = 104.dp),
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        // Top Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically
            ) {
                Image(
                    painter = painterResource(R.drawable.ic_tabis_logo),
                    contentDescription = "Tabis VPN",
                    modifier = Modifier
                        .size(38.dp)
                        .clip(CircleShape)
                        .border(1.5.dp, borderColor, CircleShape)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        text = "Tabis VPN",
                        color = textColor,
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 15.sp
                    )
                    Text(
                        text = "PROTECTED TUNNEL",
                        color = textDim,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp,
                        letterSpacing = 1.sp
                    )
                }
            }

            // Status Badge
            Row(
                modifier = Modifier
                    .clip(TabisShapes.Badge)
                    .background(badgeBg)
                    .border(0.5.dp, borderColor, TabisShapes.Badge)
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(6.dp)
                        .clip(CircleShape)
                        .background(if (isRunning) TabisColors.ConnectedGreen else TabisColors.DisconnectedRed)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = if (isRunning) stringResource(R.string.tabis_status_connected)
                    else stringResource(R.string.tabis_status_disconnected),
                    color = textMuted,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium
                )
            }
        }

        if (showZeroBalanceBanner) {
            Spacer(modifier = Modifier.height(16.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(TabisShapes.InnerCard)
                    .background(TabisColors.DisconnectedRed.copy(alpha = 0.12f))
                    .border(1.dp, TabisColors.DisconnectedRed.copy(alpha = 0.4f), TabisShapes.InnerCard)
                    .clickable { onNavigateToProfile() }
                    .padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(TabisColors.DisconnectedRed)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        text = stringResource(R.string.tabis_banner_zero_balance),
                        color = textColor,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.weight(1f)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "ПОПОЛНИТЬ",
                        color = TabisColors.AccentBlue,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(28.dp))

        // Hero Center Section
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = stringResource(R.string.tabis_security_status),
                color = textDim,
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp,
                letterSpacing = 1.5.sp,
                fontWeight = FontWeight.Medium
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = if (isRunning) stringResource(R.string.tabis_secured) else stringResource(R.string.tabis_unsecured),
                color = textColor,
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = if (isRunning) stringResource(R.string.tabis_secured_desc)
                else stringResource(R.string.tabis_unsecured_desc),
                color = textMuted,
                fontSize = 13.sp,
                modifier = Modifier.padding(horizontal = 16.dp),
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )

            // Active Stats Card (Visible when connected)
            AnimatedVisibility(visible = isRunning) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 20.dp)
                        .clip(TabisShapes.InnerCard)
                        .background(cardSubtle)
                        .border(0.5.dp, borderColor, TabisShapes.InnerCard)
                        .padding(16.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceAround
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = stringResource(R.string.tabis_stat_uptime),
                                color = textDim,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 10.sp
                            )
                            Text(
                                text = uptimeStr,
                                color = textColor,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.padding(top = 2.dp)
                            )
                        }
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = stringResource(R.string.tabis_stat_status),
                                color = textDim,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 10.sp
                            )
                            Text(
                                text = stringResource(R.string.tabis_status_active),
                                color = TabisColors.ConnectedGreen,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.padding(top = 2.dp)
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(28.dp))

            // Massive Buro Pill Action Button
            Button(
                onClick = { handleConnectTap() },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(64.dp),
                shape = TabisShapes.Pill,
                colors = ButtonDefaults.buttonColors(
                    containerColor = TabisColors.AccentBlue
                ),
                elevation = ButtonDefaults.buttonElevation(defaultElevation = 2.dp),
                enabled = !isCheckingEligibility
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center
                ) {
                    if (isCheckingEligibility) {
                        androidx.compose.material3.CircularProgressIndicator(
                            color = Color.White,
                            modifier = Modifier.size(24.dp),
                            strokeWidth = 2.5.dp
                        )
                    } else {
                        Icon(
                            painter = painterResource(R.drawable.ic_tabis_bolt),
                            contentDescription = null,
                            tint = Color.White,
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = if (isRunning) stringResource(R.string.tabis_btn_disconnect)
                            else stringResource(R.string.tabis_btn_connect),
                            color = Color.White,
                            fontSize = 17.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(28.dp))

        // Selected Server Card (Clean & Minimalist: masked as "Сервер #1", no location or ping exposed)
        Column(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.tabis_selected_node),
                color = textDim,
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp,
                letterSpacing = 1.sp,
                modifier = Modifier.padding(start = 4.dp, bottom = 8.dp)
            )

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(TabisShapes.Card)
                    .background(cardBg)
                    .border(0.5.dp, borderColor, TabisShapes.Card)
                    .clickable(onClick = onOpenServerPicker)
                    .padding(20.dp)
            ) {
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
                                painter = painterResource(R.drawable.ic_tabis_shield),
                                contentDescription = null,
                                tint = TabisColors.AccentBlue,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(14.dp))
                        Column {
                            val displayName = selectedServer?.let {
                                TabisSecurityManager.getServerDisplayName(it.guid)
                            } ?: "Сервер #1"

                            Text(
                                text = displayName,
                                color = textColor,
                                fontSize = 15.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                text = "Нажмите для выбора сервера",
                                color = textMuted,
                                fontSize = 11.sp,
                                modifier = Modifier.padding(top = 2.dp)
                            )
                        }
                    }

                    Box(
                        modifier = Modifier
                            .clip(CircleShape)
                            .background(badgeBg)
                            .border(0.5.dp, borderColor, CircleShape)
                            .padding(horizontal = 10.dp, vertical = 5.dp)
                    ) {
                        Text(
                            text = "СМЕНИТЬ",
                            color = TabisColors.AccentBlue,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
        }
    }
}
