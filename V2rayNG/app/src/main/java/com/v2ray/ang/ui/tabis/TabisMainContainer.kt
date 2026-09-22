package com.v2ray.ang.ui.tabis

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.ime
import androidx.compose.ui.platform.LocalDensity
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
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.v2ray.ang.R
import com.v2ray.ang.extension.toastError
import com.v2ray.ang.ui.compose.LocalDarkTheme
import com.v2ray.ang.ui.main.MainAction
import com.v2ray.ang.ui.main.MainDestination
import com.v2ray.ang.ui.main.MainDrawerContent
import com.v2ray.ang.ui.main.MainViewModel
import com.v2ray.ang.ui.tabis.theme.TabisColors
import com.v2ray.ang.ui.tabis.theme.TabisShapes
import com.v2ray.ang.ui.tabis.theme.TabisTheme
import kotlinx.coroutines.launch

private enum class TabisNavTab {
    Home,
    Devices,
    Apps,
    Profile,
    Support
}

@Composable
fun TabisMainContainer(
    mainViewModel: MainViewModel,
    onAction: (MainAction) -> Unit,
    onNavigate: (MainDestination) -> Unit,
    onRefreshServers: () -> Unit = {}
) {
    val isDarkTheme = LocalDarkTheme.current
    val uiState by mainViewModel.uiState.collectAsStateWithLifecycle()
    val isRunning = uiState.isRunning
    val displayText = mainViewModel.formatStatus(uiState.status)
    val selectedGuid = uiState.selectedGuid
    val selectedGroupId = uiState.selectedGroupId

    val serverListFlow = remember(selectedGroupId) {
        mainViewModel.serversForGroup(selectedGroupId)
    }
    val servers by serverListFlow.collectAsStateWithLifecycle()
    val selectedServer = remember(servers, selectedGuid) {
        servers.firstOrNull { it.guid == selectedGuid } ?: servers.firstOrNull()
    }

    var showServerPicker by remember { mutableStateOf(false) }
    var currentTab by remember { mutableStateOf(TabisNavTab.Home) }
    val scope = rememberCoroutineScope()

    var isActivated by remember { mutableStateOf(TabisSecurityManager.isActivated()) }

    var updateInfo by remember { mutableStateOf<TabisAppUpdateInfo?>(null) }
    var isDownloadingUpdate by remember { mutableStateOf(false) }
    var downloadProgress by remember { mutableIntStateOf(0) }
    val context = androidx.compose.ui.platform.LocalContext.current

    androidx.compose.runtime.LaunchedEffect(Unit) {
        val info = TabisUpdateManager.checkForAppUpdate()
        if (info != null && info.hasUpdate) {
            updateInfo = info
        }
    }

    TabisTheme(darkTheme = isDarkTheme) {
        if (!isActivated) {
            val bg = if (isDarkTheme) TabisColors.DarkBg else TabisColors.LightBg
            Scaffold(
                modifier = Modifier
                    .fillMaxSize()
                    .background(bg),
                containerColor = bg
            ) { innerPadding ->
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(innerPadding)
                        .consumeWindowInsets(innerPadding)
                ) {
                    TabisAuthScreen(
                        isDarkTheme = isDarkTheme,
                        onActivationSuccess = {
                            isActivated = true
                            onRefreshServers()
                        }
                    )
                }
            }
        } else {
            val bg = if (isDarkTheme) TabisColors.DarkBg else TabisColors.LightBg
            val navBg = if (isDarkTheme) TabisColors.DarkNavBg else TabisColors.LightNavBg
            val borderColor = if (isDarkTheme) TabisColors.DarkBorder else TabisColors.LightBorder

            Scaffold(
                modifier = Modifier
                    .fillMaxSize()
                    .background(bg),
                containerColor = bg
            ) { innerPadding ->
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(innerPadding)
                        .consumeWindowInsets(innerPadding)
                ) {
                    // Animated page transition container
                    AnimatedContent(
                        targetState = currentTab,
                        transitionSpec = {
                            if (targetState.ordinal > initialState.ordinal) {
                                (slideInHorizontally { width -> width } + fadeIn()).togetherWith(
                                    slideOutHorizontally { width -> -width } + fadeOut()
                                )
                            } else {
                                (slideInHorizontally { width -> -width } + fadeIn()).togetherWith(
                                    slideOutHorizontally { width -> width } + fadeOut()
                                )
                            }
                        },
                        label = "TabisPageTransition"
                    ) { targetTab ->
                        when (targetTab) {
                            TabisNavTab.Home -> {
                                TabisHomeScreen(
                                    isRunning = isRunning,
                                    status = uiState.status,
                                    displayText = displayText,
                                    selectedServer = selectedServer,
                                    serversCount = servers.size,
                                    isDarkTheme = isDarkTheme,
                                    onAction = onAction,
                                    onOpenServerPicker = { showServerPicker = true },
                                    onOpenDrawer = {},
                                    onNavigateToProfile = { currentTab = TabisNavTab.Profile }
                                )
                            }
                            TabisNavTab.Devices -> {
                                TabisDevicesScreen(
                                    isDarkTheme = isDarkTheme,
                                    onNavigateToProfile = { currentTab = TabisNavTab.Profile }
                                )
                            }
                            TabisNavTab.Apps -> {
                                TabisSplitScreen(
                                    isDarkTheme = isDarkTheme
                                )
                            }
                            TabisNavTab.Profile -> {
                                TabisProfileScreen(
                                    isDarkTheme = isDarkTheme,
                                    onLogout = {
                                        isActivated = false
                                        currentTab = TabisNavTab.Home
                                    }
                                )
                            }
                            TabisNavTab.Support -> {
                                TabisSupportScreen(
                                    isDarkTheme = isDarkTheme
                                )
                            }
                        }
                    }

                    // Floating Pill Bottom Navigation Bar (5 Tabs)
                    val isKeyboardOpen = WindowInsets.ime.getBottom(LocalDensity.current) > 0
                    AnimatedVisibility(
                        visible = !isKeyboardOpen,
                        enter = fadeIn() + slideInVertically { it },
                        exit = fadeOut() + slideOutVertically { it },
                        modifier = Modifier.align(Alignment.BottomCenter)
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(start = 16.dp, end = 16.dp, bottom = 16.dp)
                        ) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(64.dp)
                                    .clip(TabisShapes.Pill)
                                    .background(navBg)
                                    .border(0.5.dp, borderColor, TabisShapes.Pill)
                                    .padding(horizontal = 4.dp, vertical = 6.dp)
                            ) {
                                Row(
                                    modifier = Modifier.fillMaxSize(),
                                    horizontalArrangement = Arrangement.SpaceEvenly,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    // Tab 1: Home
                                    BottomNavItem(
                                        title = stringResource(R.string.tabis_tab_home),
                                        iconRes = R.drawable.ic_tabis_shield,
                                        isSelected = currentTab == TabisNavTab.Home,
                                        isDarkTheme = isDarkTheme,
                                        onClick = { currentTab = TabisNavTab.Home }
                                    )

                                    // Tab 2: Devices
                                    BottomNavItem(
                                        title = stringResource(R.string.tabis_tab_devices),
                                        iconRes = R.drawable.ic_tabis_devices,
                                        isSelected = currentTab == TabisNavTab.Devices,
                                        isDarkTheme = isDarkTheme,
                                        onClick = { currentTab = TabisNavTab.Devices }
                                    )

                                    // Tab 3: Split Tunneling (Apps)
                                    BottomNavItem(
                                        title = stringResource(R.string.tabis_tab_apps),
                                        iconRes = R.drawable.ic_tabis_apps,
                                        isSelected = currentTab == TabisNavTab.Apps,
                                        isDarkTheme = isDarkTheme,
                                        onClick = { currentTab = TabisNavTab.Apps }
                                    )

                                    // Tab 4: Profile
                                    BottomNavItem(
                                        title = stringResource(R.string.tabis_profile_title),
                                        iconRes = R.drawable.ic_tabis_profile,
                                        isSelected = currentTab == TabisNavTab.Profile,
                                        isDarkTheme = isDarkTheme,
                                        onClick = { currentTab = TabisNavTab.Profile }
                                    )

                                    // Tab 5: Support
                                    BottomNavItem(
                                        title = stringResource(R.string.tabis_tab_support),
                                        iconRes = R.drawable.ic_tabis_chat,
                                        isSelected = currentTab == TabisNavTab.Support,
                                        isDarkTheme = isDarkTheme,
                                        onClick = { currentTab = TabisNavTab.Support }
                                    )
                                }
                            }
                        }
                    }

                    if (showServerPicker) {
                        TabisServerPickerSheet(
                            servers = servers,
                            selectedGuid = selectedGuid,
                            isDarkTheme = isDarkTheme,
                            onSelectServer = { guid ->
                                onAction(MainAction.SelectServer(guid))
                            },
                            onRefreshServers = onRefreshServers,
                            onDismiss = { showServerPicker = false }
                        )
                    }
                }
            }
        }

        // IN-APP UPDATE DIALOG
        updateInfo?.let { update ->
            androidx.compose.material3.AlertDialog(
                onDismissRequest = {
                    if (!isDownloadingUpdate) updateInfo = null
                },
                title = {
                    androidx.compose.material3.Text(
                        text = androidx.compose.ui.res.stringResource(com.v2ray.ang.R.string.tabis_update_title),
                        color = if (isDarkTheme) TabisColors.DarkText else TabisColors.LightText,
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
                    )
                },
                text = {
                    androidx.compose.foundation.layout.Column(
                        verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(10.dp)
                    ) {
                        androidx.compose.material3.Text(
                            text = androidx.compose.ui.res.stringResource(
                                com.v2ray.ang.R.string.tabis_update_desc,
                                update.latestVersionName
                            ),
                            color = if (isDarkTheme) TabisColors.DarkTextMuted else TabisColors.LightTextMuted
                        )

                        if (update.changelog.isNotBlank()) {
                            androidx.compose.material3.Text(
                                text = update.changelog,
                                color = TabisColors.AccentBlue,
                                fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                                fontSize = 12.sp
                            )
                        }

                        if (isDownloadingUpdate) {
                            androidx.compose.foundation.layout.Spacer(modifier = Modifier.height(8.dp))
                            androidx.compose.material3.LinearProgressIndicator(
                                progress = { downloadProgress / 100f },
                                modifier = Modifier.fillMaxWidth(),
                                color = TabisColors.AccentBlue
                            )
                            androidx.compose.material3.Text(
                                text = if (downloadProgress >= 100) {
                                    androidx.compose.ui.res.stringResource(com.v2ray.ang.R.string.tabis_update_installing)
                                } else {
                                    androidx.compose.ui.res.stringResource(
                                        com.v2ray.ang.R.string.tabis_update_downloading,
                                        downloadProgress
                                    )
                                },
                                fontSize = 12.sp,
                                color = if (isDarkTheme) TabisColors.DarkTextMuted else TabisColors.LightTextMuted
                            )
                        }
                    }
                },
                confirmButton = {
                    if (!isDownloadingUpdate) {
                        androidx.compose.material3.Button(
                            onClick = {
                                isDownloadingUpdate = true
                                downloadProgress = 0
                                scope.launch {
                                    val success = TabisUpdateManager.downloadAndInstallApk(
                                        context = context,
                                        downloadUrl = update.downloadUrl,
                                        onProgress = { p -> downloadProgress = p }
                                    )
                                    isDownloadingUpdate = false
                                    if (success) {
                                        updateInfo = null
                                    } else {
                                        context.toastError(
                                            com.v2ray.ang.R.string.tabis_update_failed
                                        )
                                    }
                                }
                            },
                            colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                                containerColor = TabisColors.AccentBlue,
                                contentColor = androidx.compose.ui.graphics.Color.White
                            )
                        ) {
                            androidx.compose.material3.Text(
                                text = androidx.compose.ui.res.stringResource(com.v2ray.ang.R.string.tabis_update_btn_update),
                                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
                            )
                        }
                    }
                },
                dismissButton = {
                    if (!isDownloadingUpdate) {
                        androidx.compose.material3.TextButton(
                            onClick = { updateInfo = null }
                        ) {
                            androidx.compose.material3.Text(
                                text = androidx.compose.ui.res.stringResource(com.v2ray.ang.R.string.tabis_update_btn_later),
                                color = if (isDarkTheme) TabisColors.DarkTextMuted else TabisColors.LightTextMuted
                            )
                        }
                    }
                },
                containerColor = if (isDarkTheme) TabisColors.DarkCard else TabisColors.LightCard
            )
        }
    }
}

@Composable
private fun BottomNavItem(
    title: String,
    iconRes: Int,
    isSelected: Boolean,
    isDarkTheme: Boolean,
    onClick: () -> Unit
) {
    val textMuted = if (isDarkTheme) TabisColors.DarkTextMuted else TabisColors.LightTextMuted
    val activeBg = TabisColors.AccentBlueBg
    val activeColor = TabisColors.AccentBlue

    Box(
        modifier = Modifier
            .clip(CircleShape)
            .background(if (isSelected) activeBg else Color.Transparent)
            .clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center
        ) {
            Icon(
                painter = painterResource(iconRes),
                contentDescription = title,
                tint = if (isSelected) activeColor else textMuted,
                modifier = Modifier.size(20.dp)
            )
            if (isSelected) {
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = title,
                    color = activeColor,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold
                )
            }
        }
    }
}
