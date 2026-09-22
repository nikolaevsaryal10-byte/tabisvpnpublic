package com.v2ray.ang.ui.tabis

import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
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
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.v2ray.ang.R
import com.v2ray.ang.ui.tabis.theme.TabisColors
import com.v2ray.ang.ui.tabis.theme.TabisShapes
import kotlinx.coroutines.launch

private enum class AuthTab {
    LOGIN,
    CODE,
    REGISTER
}

@Composable
fun TabisAuthScreen(
    isDarkTheme: Boolean,
    onActivationSuccess: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current

    val textColor = if (isDarkTheme) TabisColors.DarkText else TabisColors.LightText
    val textMuted = if (isDarkTheme) TabisColors.DarkTextMuted else TabisColors.LightTextMuted
    val textDim = if (isDarkTheme) TabisColors.DarkTextDim else TabisColors.LightTextDim
    val cardBg = if (isDarkTheme) TabisColors.DarkCard else TabisColors.LightCard
    val cardSubtle = if (isDarkTheme) TabisColors.DarkCardSubtle else TabisColors.LightCardSubtle
    val borderColor = if (isDarkTheme) TabisColors.DarkBorder else TabisColors.LightBorder

    var selectedTab by remember { mutableStateOf(AuthTab.LOGIN) }
    var showSupportOverlay by remember { mutableStateOf(false) }

    if (showSupportOverlay) {
        TabisSupportScreen(
            isDarkTheme = isDarkTheme,
            onBackClick = { showSupportOverlay = false }
        )
        return
    }

    // --- LOGIN STATE ---
    var loginEmail by remember { mutableStateOf("") }
    var loginPassword by remember { mutableStateOf("") }
    var loginPasswordVisible by remember { mutableStateOf(false) }
    var isLoggingIn by remember { mutableStateOf(false) }
    var loginError by remember { mutableStateOf<String?>(null) }

    // --- CODE ACTIVATION STATE ---
    var deviceCodeInput by remember { mutableStateOf("") }
    var isCodeActivating by remember { mutableStateOf(false) }
    var codeError by remember { mutableStateOf<String?>(null) }

    // Forgot password state
    var showForgotPasswordDialog by remember { mutableStateOf(false) }
    var forgotEmail by remember { mutableStateOf("") }
    var forgotOtp by remember { mutableStateOf("") }
    var forgotNewPassword by remember { mutableStateOf("") }
    var forgotPasswordVisible by remember { mutableStateOf(false) }
    var forgotStep by remember { mutableIntStateOf(1) } // 1: Email, 2: OTP + New Password
    var isForgotLoading by remember { mutableStateOf(false) }

    // --- REGISTER STATE ---
    // Step 1: Email + checkboxes
    // Step 2: OTP
    // Step 3: Nickname + Password
    var regStep by remember { mutableIntStateOf(1) }
    var regEmail by remember { mutableStateOf("") }
    var regTermsAgreed by remember { mutableStateOf(false) }
    var regPrivacyAgreed by remember { mutableStateOf(false) }
    var regOtp by remember { mutableStateOf("") }
    var regToken by remember { mutableStateOf("") }
    var regNickname by remember { mutableStateOf("") }
    var regPassword by remember { mutableStateOf("") }
    var regPasswordVisible by remember { mutableStateOf(false) }
    var isRegLoading by remember { mutableStateOf(false) }
    var regError by remember { mutableStateOf<String?>(null) }
    var activeLegalDoc by remember { mutableStateOf<TabisLegalDocType?>(null) }

    if (activeLegalDoc != null) {
        TabisLegalDocDialog(
            docType = activeLegalDoc!!,
            isDarkTheme = isDarkTheme,
            onDismiss = { activeLegalDoc = null }
        )
    }

    // --- FORGOT PASSWORD DIALOG ---
    if (showForgotPasswordDialog) {
        AlertDialog(
            onDismissRequest = { if (!isForgotLoading) showForgotPasswordDialog = false },
            title = {
                Text(
                    text = stringResource(R.string.tabis_auth_reset_pwd_title),
                    fontWeight = FontWeight.Bold,
                    color = textColor
                )
            },
            text = {
                Column {
                    if (forgotStep == 1) {
                        Text(
                            text = stringResource(R.string.tabis_auth_reset_pwd_desc),
                            color = textMuted,
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        OutlinedTextField(
                            value = forgotEmail,
                            onValueChange = { forgotEmail = it },
                            placeholder = { Text(stringResource(R.string.tabis_auth_email_hint), color = textDim) },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
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
                    } else {
                        Text(
                            text = "Код подтверждения отправлен на $forgotEmail",
                            color = textMuted,
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        OutlinedTextField(
                            value = forgotOtp,
                            onValueChange = { if (it.length <= 6) forgotOtp = it },
                            placeholder = { Text(stringResource(R.string.tabis_auth_otp_hint), color = textDim) },
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
                        Spacer(modifier = Modifier.height(12.dp))
                        OutlinedTextField(
                            value = forgotNewPassword,
                            onValueChange = { forgotNewPassword = it },
                            placeholder = { Text(stringResource(R.string.tabis_auth_reset_new_pwd_hint), color = textDim) },
                            visualTransformation = if (forgotPasswordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                            trailingIcon = {
                                IconButton(onClick = { forgotPasswordVisible = !forgotPasswordVisible }) {
                                    Icon(
                                        painter = painterResource(if (forgotPasswordVisible) R.drawable.ic_tabis_eye else R.drawable.ic_tabis_eye_off),
                                        contentDescription = null,
                                        tint = textDim,
                                        modifier = Modifier.size(20.dp)
                                    )
                                }
                            },
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
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (forgotStep == 1) {
                            isForgotLoading = true
                            scope.launch {
                                val (success, msg) = TabisSecurityManager.resetPasswordSendOtp(forgotEmail.trim())
                                isForgotLoading = false
                                if (success) {
                                    forgotStep = 2
                                } else {
                                    Toast.makeText(context, msg.ifBlank { "Ошибка отправки кода" }, Toast.LENGTH_SHORT).show()
                                }
                            }
                        } else {
                            isForgotLoading = true
                            scope.launch {
                                val (success, msg) = TabisSecurityManager.resetPasswordComplete(
                                    forgotEmail.trim(),
                                    forgotOtp.trim(),
                                    forgotNewPassword
                                )
                                isForgotLoading = false
                                if (success) {
                                    showForgotPasswordDialog = false
                                    Toast.makeText(context, "Пароль успешно обновлен! Выполните вход.", Toast.LENGTH_LONG).show()
                                } else {
                                    Toast.makeText(context, msg.ifBlank { "Ошибка обновления пароля" }, Toast.LENGTH_SHORT).show()
                                }
                            }
                        }
                    },
                    enabled = if (forgotStep == 1) forgotEmail.contains("@") && !isForgotLoading
                    else forgotOtp.trim().length >= 4 && forgotNewPassword.length >= 6 && !isForgotLoading,
                    shape = TabisShapes.Pill,
                    colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                ) {
                    if (isForgotLoading) {
                        CircularProgressIndicator(color = Color.White, modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                    } else {
                        Text(if (forgotStep == 1) stringResource(R.string.tabis_auth_btn_send_code) else stringResource(R.string.tabis_auth_btn_save_new_pwd), color = Color.White)
                    }
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { showForgotPasswordDialog = false },
                    enabled = !isForgotLoading
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
            .padding(horizontal = 24.dp, vertical = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Logo Badge
        Box(
            modifier = Modifier
                .size(68.dp)
                .clip(TabisShapes.InnerCard)
                .background(TabisColors.AccentBlue),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "T",
                color = Color.White,
                fontSize = 34.sp,
                fontWeight = FontWeight.Black
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        Text(
            text = "Tabis VPN",
            fontSize = 26.sp,
            fontWeight = FontWeight.ExtraBold,
            color = textColor,
            letterSpacing = (-0.5).sp
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Switch Tabs: Вход / По коду / Регистрация
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(TabisShapes.Pill)
                .background(cardSubtle)
                .border(0.5.dp, borderColor, TabisShapes.Pill)
                .padding(4.dp)
        ) {
            Row(modifier = Modifier.fillMaxWidth()) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(TabisShapes.Pill)
                        .background(if (selectedTab == AuthTab.LOGIN) TabisColors.AccentBlue else Color.Transparent)
                        .clickable {
                            selectedTab = AuthTab.LOGIN
                            loginError = null
                        }
                        .padding(vertical = 10.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = stringResource(R.string.tabis_auth_login_tab),
                        color = if (selectedTab == AuthTab.LOGIN) Color.White else textMuted,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(TabisShapes.Pill)
                        .background(if (selectedTab == AuthTab.CODE) TabisColors.AccentBlue else Color.Transparent)
                        .clickable {
                            selectedTab = AuthTab.CODE
                            codeError = null
                        }
                        .padding(vertical = 10.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = stringResource(R.string.tabis_auth_code_tab),
                        color = if (selectedTab == AuthTab.CODE) Color.White else textMuted,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(TabisShapes.Pill)
                        .background(if (selectedTab == AuthTab.REGISTER) TabisColors.AccentBlue else Color.Transparent)
                        .clickable {
                            selectedTab = AuthTab.REGISTER
                            regError = null
                        }
                        .padding(vertical = 10.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = stringResource(R.string.tabis_auth_register_tab),
                        color = if (selectedTab == AuthTab.REGISTER) Color.White else textMuted,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        // Card Container
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(TabisShapes.Card)
                .background(cardBg)
                .border(0.5.dp, borderColor, TabisShapes.Card)
                .padding(22.dp)
        ) {
            if (selectedTab == AuthTab.LOGIN) {
                // --- LOGIN FORM ---
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    OutlinedTextField(
                        value = loginEmail,
                        onValueChange = {
                            loginEmail = it
                            loginError = null
                        },
                        placeholder = { Text(stringResource(R.string.tabis_auth_email_hint), color = textDim) },
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Email,
                            imeAction = ImeAction.Next
                        ),
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

                    OutlinedTextField(
                        value = loginPassword,
                        onValueChange = {
                            loginPassword = it
                            loginError = null
                        },
                        placeholder = { Text(stringResource(R.string.tabis_auth_password_hint), color = textDim) },
                        visualTransformation = if (loginPasswordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Password,
                            imeAction = ImeAction.Done
                        ),
                        keyboardActions = KeyboardActions(
                            onDone = { focusManager.clearFocus() }
                        ),
                        trailingIcon = {
                            IconButton(onClick = { loginPasswordVisible = !loginPasswordVisible }) {
                                Icon(
                                    painter = painterResource(if (loginPasswordVisible) R.drawable.ic_tabis_eye else R.drawable.ic_tabis_eye_off),
                                    contentDescription = null,
                                    tint = textDim,
                                    modifier = Modifier.size(20.dp)
                                )
                            }
                        },
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

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 4.dp),
                        horizontalArrangement = Arrangement.End
                    ) {
                        TextButton(
                            onClick = {
                                forgotStep = 1
                                forgotEmail = loginEmail.trim()
                                forgotOtp = ""
                                forgotNewPassword = ""
                                showForgotPasswordDialog = true
                            }
                        ) {
                            Text(
                                text = stringResource(R.string.tabis_auth_forgot_password),
                                color = TabisColors.AccentBlue,
                                fontSize = 12.sp
                            )
                        }
                    }

                    if (loginError != null) {
                        Text(
                            text = loginError ?: "",
                            color = TabisColors.DisconnectedRed,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.padding(bottom = 10.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Button(
                        onClick = {
                            focusManager.clearFocus()
                            isLoggingIn = true
                            loginError = null
                            scope.launch {
                                val (success, msg) = TabisSecurityManager.login(loginEmail.trim(), loginPassword)
                                isLoggingIn = false
                                if (success) {
                                    onActivationSuccess()
                                } else {
                                    loginError = msg.ifBlank { "Неверный логин или пароль" }
                                }
                            }
                        },
                        enabled = loginEmail.isNotBlank() && loginPassword.isNotBlank() && !isLoggingIn,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(54.dp),
                        shape = TabisShapes.Pill,
                        colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                    ) {
                        if (isLoggingIn) {
                            CircularProgressIndicator(color = Color.White, modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
                        } else {
                            Text(
                                text = stringResource(R.string.tabis_auth_btn_login),
                                color = Color.White,
                                fontSize = 15.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }
            } else if (selectedTab == AuthTab.CODE) {
                // --- CODE ACTIVATION / LOGIN ---
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text = stringResource(R.string.tabis_auth_code_desc),
                        color = textMuted,
                        fontSize = 13.sp,
                        lineHeight = 18.sp,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(bottom = 18.dp)
                    )

                    OutlinedTextField(
                        value = deviceCodeInput,
                        onValueChange = {
                            deviceCodeInput = it.uppercase()
                            codeError = null
                        },
                        placeholder = { Text(stringResource(R.string.tabis_auth_code_hint), color = textDim) },
                        keyboardOptions = KeyboardOptions(
                            capitalization = KeyboardCapitalization.Characters,
                            imeAction = ImeAction.Done
                        ),
                        keyboardActions = KeyboardActions(
                            onDone = { focusManager.clearFocus() }
                        ),
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

                    if (codeError != null) {
                        Spacer(modifier = Modifier.height(10.dp))
                        Text(
                            text = codeError!!,
                            color = TabisColors.DisconnectedRed,
                            fontSize = 12.sp,
                            textAlign = TextAlign.Center
                        )
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    Button(
                        onClick = {
                            val clean = deviceCodeInput.trim().uppercase()
                            if (clean.isBlank()) {
                                codeError = "Введите код устройства"
                                return@Button
                            }
                            isCodeActivating = true
                            codeError = null
                            focusManager.clearFocus()
                            scope.launch {
                                val (success, msg) = TabisSecurityManager.activateToken(clean)
                                isCodeActivating = false
                                if (success) {
                                    Toast.makeText(context, "Устройство успешно подключено!", Toast.LENGTH_SHORT).show()
                                    onActivationSuccess()
                                } else {
                                    codeError = msg
                                }
                            }
                        },
                        enabled = !isCodeActivating && deviceCodeInput.isNotBlank(),
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(54.dp),
                        shape = TabisShapes.Pill,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = TabisColors.AccentBlue
                        )
                    ) {
                        if (isCodeActivating) {
                            CircularProgressIndicator(
                                color = Color.White,
                                modifier = Modifier.size(22.dp),
                                strokeWidth = 2.dp
                            )
                        } else {
                            Text(
                                text = stringResource(R.string.tabis_auth_code_btn),
                                color = Color.White,
                                fontSize = 15.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }
            } else {
                // --- REGISTRATION FLOW ---
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    when (regStep) {
                        1 -> {
                            // Step 1: Email + Checkboxes
                            OutlinedTextField(
                                value = regEmail,
                                onValueChange = {
                                    regEmail = it
                                    regError = null
                                },
                                placeholder = { Text(stringResource(R.string.tabis_auth_email_hint), color = textDim) },
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Done),
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
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier
                                        .weight(1f)
                                        .clickable { regTermsAgreed = !regTermsAgreed }
                                ) {
                                    Checkbox(
                                        checked = regTermsAgreed,
                                        onCheckedChange = { regTermsAgreed = it },
                                        colors = CheckboxDefaults.colors(checkedColor = TabisColors.AccentBlue)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        text = stringResource(R.string.tabis_auth_terms_agreement),
                                        color = textMuted,
                                        fontSize = 11.sp,
                                        lineHeight = 15.sp
                                    )
                                }
                                TextButton(
                                    onClick = { activeLegalDoc = TabisLegalDocType.TERMS },
                                    contentPadding = PaddingValues(horizontal = 6.dp, vertical = 0.dp)
                                ) {
                                    Text(
                                        text = stringResource(R.string.tabis_legal_read),
                                        color = TabisColors.AccentBlue,
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.height(4.dp))

                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier
                                        .weight(1f)
                                        .clickable { regPrivacyAgreed = !regPrivacyAgreed }
                                ) {
                                    Checkbox(
                                        checked = regPrivacyAgreed,
                                        onCheckedChange = { regPrivacyAgreed = it },
                                        colors = CheckboxDefaults.colors(checkedColor = TabisColors.AccentBlue)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        text = stringResource(R.string.tabis_auth_privacy_agreement),
                                        color = textMuted,
                                        fontSize = 11.sp,
                                        lineHeight = 15.sp
                                    )
                                }
                                TextButton(
                                    onClick = { activeLegalDoc = TabisLegalDocType.PRIVACY },
                                    contentPadding = PaddingValues(horizontal = 6.dp, vertical = 0.dp)
                                ) {
                                    Text(
                                        text = stringResource(R.string.tabis_legal_read),
                                        color = TabisColors.AccentBlue,
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }

                            if (regError != null) {
                                Spacer(modifier = Modifier.height(10.dp))
                                Text(
                                    text = regError ?: "",
                                    color = TabisColors.DisconnectedRed,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    textAlign = TextAlign.Center
                                )
                            }

                            Spacer(modifier = Modifier.height(16.dp))

                            Button(
                                onClick = {
                                    focusManager.clearFocus()
                                    isRegLoading = true
                                    regError = null
                                    scope.launch {
                                        val (success, msg) = TabisSecurityManager.registerSendOtp(regEmail.trim())
                                        isRegLoading = false
                                        if (success) {
                                            regStep = 2
                                        } else {
                                            regError = msg.ifBlank { "Ошибка отправки кода" }
                                        }
                                    }
                                },
                                enabled = regEmail.contains("@") && regTermsAgreed && regPrivacyAgreed && !isRegLoading,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(54.dp),
                                shape = TabisShapes.Pill,
                                colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                            ) {
                                if (isRegLoading) {
                                    CircularProgressIndicator(color = Color.White, modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
                                } else {
                                    Text(
                                        text = stringResource(R.string.tabis_auth_btn_send_code),
                                        color = Color.White,
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }
                        }

                        2 -> {
                            // Step 2: OTP Verification
                            Text(
                                text = "Код подтверждения отправлен на $regEmail",
                                color = textMuted,
                                fontSize = 13.sp,
                                textAlign = TextAlign.Center
                            )

                            Spacer(modifier = Modifier.height(14.dp))

                            OutlinedTextField(
                                value = regOtp,
                                onValueChange = {
                                    if (it.length <= 6) regOtp = it
                                    regError = null
                                },
                                placeholder = { Text(stringResource(R.string.tabis_auth_otp_hint), color = textDim) },
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
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

                            if (regError != null) {
                                Spacer(modifier = Modifier.height(10.dp))
                                Text(
                                    text = regError ?: "",
                                    color = TabisColors.DisconnectedRed,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    textAlign = TextAlign.Center
                                )
                            }

                            Spacer(modifier = Modifier.height(16.dp))

                            Button(
                                onClick = {
                                    focusManager.clearFocus()
                                    isRegLoading = true
                                    regError = null
                                    scope.launch {
                                        val (success, msg) = TabisSecurityManager.registerVerifyOtp(regEmail.trim(), regOtp.trim())
                                        isRegLoading = false
                                        if (success && msg.isNotBlank() && msg.startsWith("reg_")) {
                                            regToken = msg
                                            regStep = 3
                                        } else {
                                            regError = msg.ifBlank { "Неверный код" }
                                        }
                                    }
                                },
                                enabled = regOtp.trim().length >= 4 && !isRegLoading,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(54.dp),
                                shape = TabisShapes.Pill,
                                colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                            ) {
                                if (isRegLoading) {
                                    CircularProgressIndicator(color = Color.White, modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
                                } else {
                                    Text(
                                        text = "Подтвердить код",
                                        color = Color.White,
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }
                        }

                        3 -> {
                            // Step 3: Nickname and Password
                            OutlinedTextField(
                                value = regNickname,
                                onValueChange = {
                                    regNickname = it
                                    regError = null
                                },
                                placeholder = { Text(stringResource(R.string.tabis_auth_nickname_hint), color = textDim) },
                                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
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

                            OutlinedTextField(
                                value = regPassword,
                                onValueChange = {
                                    regPassword = it
                                    regError = null
                                },
                                placeholder = { Text(stringResource(R.string.tabis_auth_password_hint), color = textDim) },
                                visualTransformation = if (regPasswordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                                trailingIcon = {
                                    IconButton(onClick = { regPasswordVisible = !regPasswordVisible }) {
                                        Icon(
                                            painter = painterResource(if (regPasswordVisible) R.drawable.ic_tabis_eye else R.drawable.ic_tabis_eye_off),
                                            contentDescription = null,
                                            tint = textDim,
                                            modifier = Modifier.size(20.dp)
                                        )
                                    }
                                },
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

                            if (regError != null) {
                                Spacer(modifier = Modifier.height(10.dp))
                                Text(
                                    text = regError ?: "",
                                    color = TabisColors.DisconnectedRed,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    textAlign = TextAlign.Center
                                )
                            }

                            Spacer(modifier = Modifier.height(16.dp))

                            Button(
                                onClick = {
                                    focusManager.clearFocus()
                                    isRegLoading = true
                                    regError = null
                                    scope.launch {
                                        if (regToken.isBlank() || !regToken.startsWith("reg_")) {
                                            isRegLoading = false
                                            regError = "Сессия регистрации не подтверждена. Введите код повторно."
                                            regStep = 2
                                            return@launch
                                        }
                                        val (success, msg) = TabisSecurityManager.registerComplete(
                                            regEmail.trim(),
                                            regToken,
                                            regNickname.trim(),
                                            regPassword
                                        )
                                        isRegLoading = false
                                        if (success) {
                                            onActivationSuccess()
                                        } else {
                                            regError = msg.ifBlank { "Ошибка завершения регистрации" }
                                        }
                                    }
                                },
                                enabled = regNickname.trim().isNotBlank() && regPassword.length >= 6 && !isRegLoading,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(54.dp),
                                shape = TabisShapes.Pill,
                                colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                            ) {
                                if (isRegLoading) {
                                    CircularProgressIndicator(color = Color.White, modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
                                } else {
                                    Text(
                                        text = stringResource(R.string.tabis_auth_btn_register),
                                        color = Color.White,
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        TextButton(
            onClick = { showSupportOverlay = true },
            modifier = Modifier.align(Alignment.CenterHorizontally)
        ) {
            Icon(
                painter = painterResource(R.drawable.ic_tabis_chat),
                contentDescription = null,
                tint = TabisColors.AccentBlue,
                modifier = Modifier.size(18.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = stringResource(R.string.tabis_auth_support_btn),
                color = TabisColors.AccentBlue,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium
            )
        }
    }
}
