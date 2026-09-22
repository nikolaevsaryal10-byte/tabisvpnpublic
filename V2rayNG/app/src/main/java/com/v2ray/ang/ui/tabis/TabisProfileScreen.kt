package com.v2ray.ang.ui.tabis

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.v2ray.ang.R
import com.v2ray.ang.ui.tabis.theme.TabisColors
import com.v2ray.ang.ui.tabis.theme.TabisShapes
import kotlinx.coroutines.launch

@Composable
fun TabisProfileScreen(
    isDarkTheme: Boolean,
    onLogout: () -> Unit,
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

    var profile by remember { mutableStateOf<TabisUserProfile?>(null) }
    var isLoadingProfile by remember { mutableStateOf(false) }

    // Top up state
    var showTopUpDialog by remember { mutableStateOf(false) }
    var topUpAmountText by remember { mutableStateOf("60") }
    var agreementAccepted by remember { mutableStateOf(false) }
    var isSubmittingPayment by remember { mutableStateOf(false) }

    // Logout state
    var showLogoutDialog by remember { mutableStateOf(false) }

    // Delete account state
    var showDeleteStep1Dialog by remember { mutableStateOf(false) }
    var showDeleteStep2Dialog by remember { mutableStateOf(false) }
    var showDeleteOtpDialog by remember { mutableStateOf(false) }
    var deleteOtpInput by remember { mutableStateOf("") }
    var isDeletingAccount by remember { mutableStateOf(false) }

    // Legal doc viewer state
    var activeLegalDoc by remember { mutableStateOf<TabisLegalDocType?>(null) }

    if (activeLegalDoc != null) {
        TabisLegalDocDialog(
            docType = activeLegalDoc!!,
            isDarkTheme = isDarkTheme,
            onDismiss = { activeLegalDoc = null }
        )
    }

    fun refreshProfile() {
        isLoadingProfile = true
        scope.launch {
            val (p, _) = TabisSecurityManager.fetchProfileMe()
            if (p != null) {
                profile = p
            }
            isLoadingProfile = false
        }
    }

    LaunchedEffect(Unit) {
        refreshProfile()
    }

    fun copyToClipboard(text: String) {
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = ClipData.newPlainText("Tabis ID", text)
        clipboard.setPrimaryClip(clip)
        Toast.makeText(context, context.getString(R.string.tabis_profile_copied_id), Toast.LENGTH_SHORT).show()
    }

    // --- TOP UP DIALOG ---
    if (showTopUpDialog) {
        AlertDialog(
            onDismissRequest = { if (!isSubmittingPayment) showTopUpDialog = false },
            title = {
                Text(
                    text = stringResource(R.string.tabis_profile_topup_dialog_title),
                    fontWeight = FontWeight.Bold,
                    color = textColor
                )
            },
            text = {
                Column {
                    Text(
                        text = stringResource(R.string.tabis_profile_topup_amount_label),
                        color = textDim,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp,
                        letterSpacing = 1.sp
                    )
                    Spacer(modifier = Modifier.height(6.dp))

                    OutlinedTextField(
                        value = topUpAmountText,
                        onValueChange = { input ->
                            val filtered = input.filter { it.isDigit() }
                            topUpAmountText = filtered
                        },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
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

                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { agreementAccepted = !agreementAccepted }
                    ) {
                        Checkbox(
                            checked = agreementAccepted,
                            onCheckedChange = { agreementAccepted = it },
                            colors = CheckboxDefaults.colors(checkedColor = TabisColors.AccentBlue)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = stringResource(R.string.tabis_profile_agreement_text),
                            color = textMuted,
                            fontSize = 12.sp,
                            lineHeight = 16.sp
                        )
                    }

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(start = 36.dp, top = 4.dp),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Text(
                            text = stringResource(R.string.tabis_legal_read_terms),
                            color = TabisColors.AccentBlue,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Medium,
                            modifier = Modifier.clickable { activeLegalDoc = TabisLegalDocType.TERMS }
                        )
                        Text(
                            text = "•",
                            color = textDim,
                            fontSize = 11.sp
                        )
                        Text(
                            text = stringResource(R.string.tabis_legal_read_privacy),
                            color = TabisColors.AccentBlue,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Medium,
                            modifier = Modifier.clickable { activeLegalDoc = TabisLegalDocType.PRIVACY }
                        )
                    }
                }
            },
            confirmButton = {
                val amount = topUpAmountText.toIntOrNull() ?: 0
                val canProceed = amount >= 60 && agreementAccepted && !isSubmittingPayment

                Button(
                    onClick = {
                        isSubmittingPayment = true
                        scope.launch {
                            val (success, payUrl) = TabisSecurityManager.topUp(amount)
                            isSubmittingPayment = false
                            if (success && payUrl.isNotBlank()) {
                                showTopUpDialog = false
                                try {
                                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(payUrl))
                                    context.startActivity(intent)
                                } catch (_: Exception) {
                                    Toast.makeText(context, "Не удалось открыть браузер", Toast.LENGTH_SHORT).show()
                                }
                            } else {
                                Toast.makeText(context, payUrl.ifBlank { "Ошибка создания платежа" }, Toast.LENGTH_SHORT).show()
                            }
                        }
                    },
                    enabled = canProceed,
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                ) {
                    if (isSubmittingPayment) {
                        CircularProgressIndicator(color = Color.White, modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                    } else {
                        Text(stringResource(R.string.tabis_profile_proceed_payment), color = Color.White)
                    }
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { showTopUpDialog = false },
                    enabled = !isSubmittingPayment
                ) {
                    Text(stringResource(R.string.tabis_dialog_cancel), color = textDim)
                }
            },
            containerColor = cardBg,
            shape = TabisShapes.Card
        )
    }

    // --- LOGOUT CONFIRMATION ---
    if (showLogoutDialog) {
        AlertDialog(
            onDismissRequest = { showLogoutDialog = false },
            title = {
                Text(
                    text = stringResource(R.string.tabis_profile_logout_btn),
                    fontWeight = FontWeight.Bold,
                    color = textColor
                )
            },
            text = {
                Text(
                    text = stringResource(R.string.tabis_profile_logout_confirm),
                    color = textMuted,
                    fontSize = 14.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showLogoutDialog = false
                        TabisSecurityManager.logout()
                        onLogout()
                    },
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.DisconnectedRed)
                ) {
                    Text(stringResource(R.string.tabis_profile_logout_btn), color = Color.White)
                }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutDialog = false }) {
                    Text(stringResource(R.string.tabis_dialog_cancel), color = textDim)
                }
            },
            containerColor = cardBg,
            shape = TabisShapes.Card
        )
    }

    // --- DELETE STEP 1 ---
    if (showDeleteStep1Dialog) {
        AlertDialog(
            onDismissRequest = { showDeleteStep1Dialog = false },
            title = {
                Text(
                    text = stringResource(R.string.tabis_profile_delete_step1_title),
                    fontWeight = FontWeight.Bold,
                    color = TabisColors.DisconnectedRed
                )
            },
            text = {
                Text(
                    text = stringResource(R.string.tabis_profile_delete_step1_msg),
                    color = textMuted,
                    fontSize = 14.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showDeleteStep1Dialog = false
                        showDeleteStep2Dialog = true
                    },
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.DisconnectedRed)
                ) {
                    Text("Да, продолжить", color = Color.White)
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteStep1Dialog = false }) {
                    Text(stringResource(R.string.tabis_dialog_cancel), color = textDim)
                }
            },
            containerColor = cardBg,
            shape = TabisShapes.Card
        )
    }

    // --- DELETE STEP 2 ---
    if (showDeleteStep2Dialog) {
        AlertDialog(
            onDismissRequest = { if (!isDeletingAccount) showDeleteStep2Dialog = false },
            title = {
                Text(
                    text = stringResource(R.string.tabis_profile_delete_step2_title),
                    fontWeight = FontWeight.Bold,
                    color = TabisColors.DisconnectedRed
                )
            },
            text = {
                Text(
                    text = stringResource(R.string.tabis_profile_delete_step2_msg),
                    color = textMuted,
                    fontSize = 14.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        isDeletingAccount = true
                        scope.launch {
                            val (success, msg) = TabisSecurityManager.deleteAccountSendOtp()
                            isDeletingAccount = false
                            if (success) {
                                showDeleteStep2Dialog = false
                                deleteOtpInput = ""
                                showDeleteOtpDialog = true
                            } else {
                                Toast.makeText(context, msg.ifBlank { "Ошибка отправки кода" }, Toast.LENGTH_SHORT).show()
                            }
                        }
                    },
                    enabled = !isDeletingAccount,
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.DisconnectedRed)
                ) {
                    if (isDeletingAccount) {
                        CircularProgressIndicator(color = Color.White, modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                    } else {
                        Text("Отправить код", color = Color.White)
                    }
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { showDeleteStep2Dialog = false },
                    enabled = !isDeletingAccount
                ) {
                    Text(stringResource(R.string.tabis_dialog_cancel), color = textDim)
                }
            },
            containerColor = cardBg,
            shape = TabisShapes.Card
        )
    }

    // --- DELETE OTP STEP ---
    if (showDeleteOtpDialog) {
        val userEmail = profile?.email ?: TabisSecurityManager.getUserEmail()

        AlertDialog(
            onDismissRequest = { if (!isDeletingAccount) showDeleteOtpDialog = false },
            title = {
                Text(
                    text = stringResource(R.string.tabis_profile_delete_otp_title),
                    fontWeight = FontWeight.Bold,
                    color = TabisColors.DisconnectedRed
                )
            },
            text = {
                Column {
                    Text(
                        text = stringResource(R.string.tabis_profile_delete_otp_msg, userEmail),
                        color = textMuted,
                        fontSize = 13.sp
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    OutlinedTextField(
                        value = deleteOtpInput,
                        onValueChange = { if (it.length <= 6) deleteOtpInput = it },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        placeholder = { Text("6-значный код", color = textDim) },
                        singleLine = true,
                        shape = TabisShapes.Input,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = TabisColors.DisconnectedRed,
                            unfocusedBorderColor = borderColor,
                            focusedTextColor = textColor,
                            unfocusedTextColor = textColor
                        ),
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        isDeletingAccount = true
                        scope.launch {
                            val (success, msg) = TabisSecurityManager.deleteAccountComplete(deleteOtpInput.trim())
                            isDeletingAccount = false
                            if (success) {
                                showDeleteOtpDialog = false
                                TabisSecurityManager.logout()
                                Toast.makeText(context, "Аккаунт успешно удален", Toast.LENGTH_LONG).show()
                                onLogout()
                            } else {
                                Toast.makeText(context, msg.ifBlank { "Неверный код" }, Toast.LENGTH_SHORT).show()
                            }
                        }
                    },
                    enabled = deleteOtpInput.trim().length >= 4 && !isDeletingAccount,
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.DisconnectedRed)
                ) {
                    if (isDeletingAccount) {
                        CircularProgressIndicator(color = Color.White, modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                    } else {
                        Text("Удалить навсегда", color = Color.White)
                    }
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { showDeleteOtpDialog = false },
                    enabled = !isDeletingAccount
                ) {
                    Text(stringResource(R.string.tabis_dialog_cancel), color = textDim)
                }
            },
            containerColor = cardBg,
            shape = TabisShapes.Card
        )
    }

    val displayEmail = profile?.email ?: TabisSecurityManager.getUserEmail()
    val displayNickname = profile?.nickname ?: TabisSecurityManager.getUserNickname()
    val displayUserCode = profile?.userCode ?: TabisSecurityManager.getUserCode()
    val displayBalance = profile?.balance ?: TabisSecurityManager.getUserBalance()
    val displayDaysRemaining = profile?.daysRemaining ?: 0
    val displayCreatedAt = profile?.createdAt?.take(10) ?: TabisSecurityManager.getUserCreatedAt().take(10)

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
                    text = stringResource(R.string.tabis_profile_title),
                    color = textColor,
                    fontWeight = FontWeight.Bold,
                    fontSize = 22.sp
                )
                Text(
                    text = "USER ACCOUNT",
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
                    .clickable { refreshProfile() }
                    .padding(horizontal = 12.dp, vertical = 6.dp)
            ) {
                Text(
                    text = if (isLoadingProfile) "ОБНОВЛЕНИЕ..." else "СИНХРОНИЗИРОВАНО",
                    color = TabisColors.ConnectedGreen,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.SemiBold
                )
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        // User Identity Card
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(TabisShapes.Card)
                .background(cardBg)
                .border(0.5.dp, borderColor, TabisShapes.Card)
                .padding(20.dp)
        ) {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(52.dp)
                            .clip(CircleShape)
                            .background(TabisColors.AccentBlueBg),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = displayNickname.take(1).uppercase().ifBlank { "U" },
                            color = TabisColors.AccentBlue,
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }

                    Spacer(modifier = Modifier.width(14.dp))

                    Column {
                        Text(
                            text = displayNickname,
                            color = textColor,
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = displayEmail.ifBlank { "Не указан" },
                            color = textMuted,
                            fontSize = 13.sp,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Copyable Account ID
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(TabisShapes.InnerCard)
                        .background(cardSubtle)
                        .border(0.5.dp, borderColor, TabisShapes.InnerCard)
                        .clickable { copyToClipboard(displayUserCode) }
                        .padding(horizontal = 14.dp, vertical = 10.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = stringResource(R.string.tabis_profile_id_label),
                                color = textDim,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 9.sp,
                                letterSpacing = 1.sp
                            )
                            Text(
                                text = displayUserCode,
                                color = textColor,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.padding(top = 2.dp)
                            )
                        }

                        Text(
                            text = "КОПИРОВАТЬ",
                            color = TabisColors.AccentBlue,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                if (displayCreatedAt.isNotBlank()) {
                    Spacer(modifier = Modifier.height(10.dp))
                    Text(
                        text = stringResource(R.string.tabis_profile_reg_date, displayCreatedAt),
                        color = textDim,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Balance & Subscription Card
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(TabisShapes.Card)
                .background(cardBg)
                .border(0.5.dp, borderColor, TabisShapes.Card)
                .padding(20.dp)
        ) {
            Column {
                Text(
                    text = stringResource(R.string.tabis_profile_balance_title),
                    color = textDim,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                    letterSpacing = 1.sp
                )

                Spacer(modifier = Modifier.height(6.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.Bottom
                ) {
                    Text(
                        text = "$displayBalance ₽",
                        color = textColor,
                        fontSize = 32.sp,
                        fontWeight = FontWeight.ExtraBold
                    )

                    Box(
                        modifier = Modifier
                            .clip(TabisShapes.Badge)
                            .background(TabisColors.AccentBlueBg)
                            .padding(horizontal = 10.dp, vertical = 5.dp)
                    ) {
                        Text(
                            text = stringResource(R.string.tabis_profile_days_remaining, displayDaysRemaining),
                            color = TabisColors.AccentBlue,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }

                Spacer(modifier = Modifier.height(18.dp))

                Button(
                    onClick = {
                        agreementAccepted = false
                        topUpAmountText = "60"
                        showTopUpDialog = true
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                ) {
                    Icon(
                        painter = painterResource(R.drawable.ic_tabis_bolt),
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = stringResource(R.string.tabis_profile_topup_btn),
                        color = Color.White,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        // Legal Documents Section
        Text(
            text = stringResource(R.string.tabis_legal_section_docs),
            color = textDim,
            fontFamily = FontFamily.Monospace,
            fontSize = 10.sp,
            letterSpacing = 1.sp,
            modifier = Modifier.padding(start = 4.dp, bottom = 10.dp)
        )

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(TabisShapes.Card)
                .background(cardBg)
                .border(0.5.dp, borderColor, TabisShapes.Card)
                .padding(vertical = 4.dp, horizontal = 16.dp)
        ) {
            Column {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { activeLegalDoc = TabisLegalDocType.TERMS }
                        .padding(vertical = 14.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            painter = painterResource(R.drawable.ic_description_24dp),
                            contentDescription = null,
                            tint = TabisColors.AccentBlue,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = stringResource(R.string.tabis_profile_terms_row),
                            color = textColor,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }
                    Text(
                        text = "›",
                        color = textDim,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )
                }

                Box(modifier = Modifier.fillMaxWidth().height(0.5.dp).background(borderColor))

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { activeLegalDoc = TabisLegalDocType.PRIVACY }
                        .padding(vertical = 14.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            painter = painterResource(R.drawable.ic_privacy_24dp),
                            contentDescription = null,
                            tint = TabisColors.AccentBlue,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = stringResource(R.string.tabis_profile_privacy_row),
                            color = textColor,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }
                    Text(
                        text = "›",
                        color = textDim,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Account Management Actions
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // Logout
            Button(
                onClick = { showLogoutDialog = true },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp),
                shape = TabisShapes.Pill,
                colors = ButtonDefaults.buttonColors(containerColor = cardBg)
            ) {
                Text(
                    text = stringResource(R.string.tabis_profile_logout_btn),
                    color = textColor,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold
                )
            }

            // Delete Account
            TextButton(
                onClick = { showDeleteStep1Dialog = true },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = stringResource(R.string.tabis_profile_delete_btn),
                    color = TabisColors.DisconnectedRed,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium
                )
            }
        }
    }
}
