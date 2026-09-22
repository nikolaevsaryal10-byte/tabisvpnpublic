package com.v2ray.ang.ui.tabis

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.v2ray.ang.R
import com.v2ray.ang.dto.entities.ServersCache
import com.v2ray.ang.ui.tabis.theme.TabisColors

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TabisServerPickerSheet(
    servers: List<ServersCache>,
    selectedGuid: String?,
    isDarkTheme: Boolean,
    onSelectServer: (String) -> Unit,
    onRefreshServers: () -> Unit = {},
    onDismiss: () -> Unit
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val textColor = if (isDarkTheme) TabisColors.DarkText else TabisColors.LightText
    val textMuted = if (isDarkTheme) TabisColors.DarkTextMuted else TabisColors.LightTextMuted
    val textDim = if (isDarkTheme) TabisColors.DarkTextDim else TabisColors.LightTextDim
    val cardBg = if (isDarkTheme) TabisColors.DarkCard else TabisColors.LightCard
    val cardSubtle = if (isDarkTheme) TabisColors.DarkCardSubtle else TabisColors.LightCardSubtle
    val borderColor = if (isDarkTheme) TabisColors.DarkBorder else TabisColors.LightBorder
    val sheetBg = if (isDarkTheme) TabisColors.DarkBg else TabisColors.LightBg

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = sheetBg
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .padding(bottom = 32.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = stringResource(R.string.tabis_sheet_servers_title),
                        color = textColor,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )

                    Text(
                        text = "${servers.size} СЕРВЕРОВ",
                        color = textDim,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp
                    )
                }

                Row(
                    modifier = Modifier
                        .clip(RoundedCornerShape(20.dp))
                        .background(cardSubtle)
                        .border(0.5.dp, borderColor, RoundedCornerShape(20.dp))
                        .clickable(onClick = onRefreshServers)
                        .padding(horizontal = 12.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        painter = painterResource(R.drawable.ic_tabis_bolt),
                        contentDescription = null,
                        tint = TabisColors.AccentBlue,
                        modifier = Modifier.size(13.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "ОБНОВИТЬ",
                        color = TabisColors.AccentBlue,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            if (servers.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 32.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = stringResource(R.string.tabis_sheet_no_servers),
                        color = textMuted,
                        fontSize = 13.sp
                    )
                }
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    itemsIndexed(servers, key = { _, item -> item.guid }) { index, server ->
                        val isSelected = server.guid == selectedGuid
                        val serverTitle = TabisSecurityManager.getServerDisplayName(server.guid, index + 1)

                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(16.dp))
                                .background(if (isSelected) cardSubtle else cardBg)
                                .border(
                                    0.5.dp,
                                    if (isSelected) TabisColors.AccentBlue else borderColor,
                                    RoundedCornerShape(16.dp)
                                )
                                .clickable {
                                    onSelectServer(server.guid)
                                    onDismiss()
                                }
                                .padding(14.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.weight(1f)
                            ) {
                                Box(
                                    modifier = Modifier
                                        .size(36.dp)
                                        .clip(CircleShape)
                                        .background(if (isSelected) TabisColors.AccentBlueBg else cardSubtle),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(
                                        painter = painterResource(R.drawable.ic_tabis_shield),
                                        contentDescription = null,
                                        tint = if (isSelected) TabisColors.AccentBlue else textMuted,
                                        modifier = Modifier.size(18.dp)
                                    )
                                }
                                Spacer(modifier = Modifier.width(12.dp))
                                Column {
                                    Text(
                                        text = serverTitle,
                                        color = textColor,
                                        fontSize = 14.sp,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium
                                    )
                                    Text(
                                        text = if (isSelected) "Активный узел" else "Нажмите для подключения",
                                        color = if (isSelected) TabisColors.AccentBlue else textMuted,
                                        fontSize = 11.sp,
                                        modifier = Modifier.padding(top = 2.dp)
                                    )
                                }
                            }

                            if (isSelected) {
                                Box(
                                    modifier = Modifier
                                        .size(8.dp)
                                        .clip(CircleShape)
                                        .background(TabisColors.AccentBlue)
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
