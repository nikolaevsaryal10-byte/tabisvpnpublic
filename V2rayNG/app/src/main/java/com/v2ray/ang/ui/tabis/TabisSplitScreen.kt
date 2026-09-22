package com.v2ray.ang.ui.tabis

import android.content.Intent
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
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
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
import com.v2ray.ang.handler.MmkvManager
import com.v2ray.ang.ui.perappproxy.PerAppProxyActivity
import com.v2ray.ang.ui.tabis.theme.TabisColors
import com.v2ray.ang.ui.tabis.theme.TabisShapes

@Composable
fun TabisSplitScreen(
    isDarkTheme: Boolean,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val textColor = if (isDarkTheme) TabisColors.DarkText else TabisColors.LightText
    val textMuted = if (isDarkTheme) TabisColors.DarkTextMuted else TabisColors.LightTextMuted
    val textDim = if (isDarkTheme) TabisColors.DarkTextDim else TabisColors.LightTextDim
    val cardBg = if (isDarkTheme) TabisColors.DarkCard else TabisColors.LightCard
    val cardSubtle = if (isDarkTheme) TabisColors.DarkCardSubtle else TabisColors.LightCardSubtle
    val borderColor = if (isDarkTheme) TabisColors.DarkBorder else TabisColors.LightBorder
    val badgeBg = if (isDarkTheme) TabisColors.DarkBadgeBg else TabisColors.LightBadgeBg

    // Read initial preferences from MMKV
    var isPerAppProxyEnabled by remember {
        mutableStateOf(MmkvManager.decodeSettingsBool(AppConfig.PREF_PER_APP_PROXY, false))
    }
    var isBypassApps by remember {
        mutableStateOf(MmkvManager.decodeSettingsBool(AppConfig.PREF_BYPASS_APPS, false))
    }
    var selectedAppsCount by remember {
        val set = MmkvManager.decodeSettingsStringSet(AppConfig.PREF_PER_APP_PROXY_SET)
        mutableStateOf(set?.size ?: 0)
    }

    // Refresh selected count when resuming
    androidx.compose.runtime.DisposableEffect(Unit) {
        val set = MmkvManager.decodeSettingsStringSet(AppConfig.PREF_PER_APP_PROXY_SET)
        selectedAppsCount = set?.size ?: 0
        onDispose {}
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp)
            .padding(top = 16.dp, bottom = 104.dp)
    ) {
        // Header
        Column(
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                text = stringResource(R.string.tabis_split_title),
                color = textColor,
                fontWeight = FontWeight.Bold,
                fontSize = 22.sp
            )

            Spacer(modifier = Modifier.height(6.dp))

            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text(
                    text = "NETWORK ROUTING",
                    color = textDim,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                    letterSpacing = 1.sp
                )

                Box(
                    modifier = Modifier
                        .clip(TabisShapes.Badge)
                        .background(badgeBg)
                        .border(0.5.dp, borderColor, TabisShapes.Badge)
                        .padding(horizontal = 10.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = if (isPerAppProxyEnabled) "АКТИВНО" else "ОТКЛЮЧЕНО",
                        color = if (isPerAppProxyEnabled) TabisColors.ConnectedGreen else textDim,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = stringResource(R.string.tabis_split_subtitle),
            color = textMuted,
            fontSize = 13.sp,
            lineHeight = 18.sp
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Master Switch Card
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(TabisShapes.Card)
                .background(cardBg)
                .border(0.5.dp, borderColor, TabisShapes.Card)
                .padding(20.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = stringResource(R.string.tabis_split_master_switch),
                        color = textColor,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    Text(
                        text = stringResource(R.string.tabis_split_master_desc),
                        color = textMuted,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(top = 3.dp)
                    )
                }

                Spacer(modifier = Modifier.width(12.dp))

                Switch(
                    checked = isPerAppProxyEnabled,
                    onCheckedChange = { checked ->
                        isPerAppProxyEnabled = checked
                        MmkvManager.encodeSettings(AppConfig.PREF_PER_APP_PROXY, checked)
                    },
                    colors = SwitchDefaults.colors(
                        checkedThumbColor = Color.White,
                        checkedTrackColor = TabisColors.AccentBlue,
                        uncheckedThumbColor = textDim,
                        uncheckedTrackColor = cardSubtle
                    )
                )
            }
        }

        if (isPerAppProxyEnabled) {
            Spacer(modifier = Modifier.height(20.dp))

            // Mode Selection Section
            Text(
                text = "РЕЖИМ МАРШРУТИЗАЦИИ",
                color = textDim,
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp,
                letterSpacing = 1.sp,
                modifier = Modifier.padding(start = 4.dp, bottom = 8.dp)
            )

            // Bypass Card
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(TabisShapes.InnerCard)
                    .background(if (isBypassApps) TabisColors.AccentBlueBg else cardBg)
                    .border(
                        if (isBypassApps) 1.dp else 0.5.dp,
                        if (isBypassApps) TabisColors.AccentBlue else borderColor,
                        TabisShapes.InnerCard
                    )
                    .clickable {
                        isBypassApps = true
                        MmkvManager.encodeSettings(AppConfig.PREF_BYPASS_APPS, true)
                    }
                    .padding(16.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(20.dp)
                            .clip(CircleShape)
                            .border(2.dp, if (isBypassApps) TabisColors.AccentBlue else textDim, CircleShape),
                        contentAlignment = Alignment.Center
                    ) {
                        if (isBypassApps) {
                            Box(
                                 modifier = Modifier
                                    .size(10.dp)
                                    .clip(CircleShape)
                                    .background(TabisColors.AccentBlue)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.width(14.dp))

                    Column {
                        Text(
                            text = stringResource(R.string.tabis_split_mode_bypass),
                            color = textColor,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            text = stringResource(R.string.tabis_split_mode_bypass_desc),
                            color = textMuted,
                            fontSize = 11.sp,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Proxy Only Card
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(TabisShapes.InnerCard)
                    .background(if (!isBypassApps) TabisColors.AccentBlueBg else cardBg)
                    .border(
                        if (!isBypassApps) 1.dp else 0.5.dp,
                        if (!isBypassApps) TabisColors.AccentBlue else borderColor,
                        TabisShapes.InnerCard
                    )
                    .clickable {
                        isBypassApps = false
                        MmkvManager.encodeSettings(AppConfig.PREF_BYPASS_APPS, false)
                    }
                    .padding(16.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(20.dp)
                            .clip(CircleShape)
                            .border(2.dp, if (!isBypassApps) TabisColors.AccentBlue else textDim, CircleShape),
                        contentAlignment = Alignment.Center
                    ) {
                        if (!isBypassApps) {
                            Box(
                                modifier = Modifier
                                    .size(10.dp)
                                    .clip(CircleShape)
                                    .background(TabisColors.AccentBlue)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.width(14.dp))

                    Column {
                        Text(
                            text = stringResource(R.string.tabis_split_mode_proxy),
                            color = textColor,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            text = stringResource(R.string.tabis_split_mode_proxy_desc),
                            color = textMuted,
                            fontSize = 11.sp,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Action Button to Open PerAppProxyActivity
            Button(
                onClick = {
                    context.startActivity(Intent(context, PerAppProxyActivity::class.java))
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                shape = TabisShapes.Pill,
                colors = ButtonDefaults.buttonColors(
                    containerColor = TabisColors.AccentBlue
                )
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center
                ) {
                    Icon(
                        painter = painterResource(R.drawable.ic_tabis_apps),
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        text = stringResource(R.string.tabis_split_manage_apps_btn),
                        color = Color.White,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Box(
                modifier = Modifier.fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = stringResource(R.string.tabis_split_apps_selected, selectedAppsCount),
                    color = textMuted,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 12.sp
                )
            }
        }
    }
}
