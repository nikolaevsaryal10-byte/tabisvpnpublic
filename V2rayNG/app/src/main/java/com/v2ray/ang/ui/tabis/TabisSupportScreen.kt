package com.v2ray.ang.ui.tabis

import android.content.Intent
import android.net.Uri
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
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
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
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.v2ray.ang.R
import com.v2ray.ang.ui.tabis.theme.TabisColors
import com.v2ray.ang.ui.tabis.theme.TabisShapes
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

private enum class SupportSection {
    CHAT,
    FAQ
}

@Composable
fun TabisSupportScreen(
    isDarkTheme: Boolean,
    modifier: Modifier = Modifier,
    onBackClick: (() -> Unit)? = null
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
    val badgeBg = if (isDarkTheme) TabisColors.DarkBadgeBg else TabisColors.LightBadgeBg

    var selectedSection by remember { mutableStateOf(SupportSection.CHAT) }
    var activeLegalDoc by remember { mutableStateOf<TabisLegalDocType?>(null) }

    // Chat states
    var messages by remember { mutableStateOf<List<TabisSupportMessage>>(emptyList()) }
    var messageInput by remember { mutableStateOf("") }
    var isSending by remember { mutableStateOf(false) }
    var isLoadingMessages by remember { mutableStateOf(false) }
    val chatListState = rememberLazyListState()

    // Polling effect for live chat
    LaunchedEffect(selectedSection) {
        if (selectedSection == SupportSection.CHAT) {
            isLoadingMessages = true
            val (_, initialMsgs) = TabisSecurityManager.fetchSupportMessages()
            messages = initialMsgs
            isLoadingMessages = false
            if (initialMsgs.isNotEmpty()) {
                chatListState.scrollToItem(initialMsgs.size - 1)
            }
            while (isActive) {
                delay(4000)
                val (ok, newMsgs) = TabisSecurityManager.fetchSupportMessages()
                if (ok && newMsgs.size != messages.size) {
                    messages = newMsgs
                    if (newMsgs.isNotEmpty()) {
                        chatListState.animateScrollToItem(newMsgs.size - 1)
                    }
                }
            }
        }
    }

    if (activeLegalDoc != null) {
        TabisLegalDocDialog(
            docType = activeLegalDoc!!,
            isDarkTheme = isDarkTheme,
            onDismiss = { activeLegalDoc = null }
        )
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp)
            .padding(top = 16.dp, bottom = 16.dp)
    ) {
        // Top Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (onBackClick != null) {
                    IconButton(
                        onClick = onBackClick,
                        modifier = Modifier
                            .padding(end = 8.dp)
                            .size(36.dp)
                    ) {
                        Icon(
                            painter = painterResource(R.drawable.ic_arrow_back_24dp),
                            contentDescription = "Back",
                            tint = textColor
                        )
                    }
                }
                Column {
                    Text(
                        text = stringResource(R.string.tabis_support_title),
                        color = textColor,
                        fontWeight = FontWeight.Bold,
                        fontSize = 22.sp
                    )
                    Text(
                        text = "CUSTOMER SERVICE",
                        color = textDim,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp,
                        letterSpacing = 1.sp
                    )
                }
            }

            Box(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(badgeBg)
                    .border(0.5.dp, borderColor, CircleShape)
                    .padding(horizontal = 12.dp, vertical = 6.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(6.dp)
                            .clip(CircleShape)
                            .background(TabisColors.ConnectedGreen)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "ОНЛАЙН",
                        color = TabisColors.ConnectedGreen,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        // Switch Tabs: Чат поддержки / FAQ и Инфо
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
                        .background(if (selectedSection == SupportSection.CHAT) TabisColors.AccentBlue else Color.Transparent)
                        .clickable { selectedSection = SupportSection.CHAT }
                        .padding(vertical = 9.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = stringResource(R.string.tabis_support_chat_tab),
                        color = if (selectedSection == SupportSection.CHAT) Color.White else textMuted,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(TabisShapes.Pill)
                        .background(if (selectedSection == SupportSection.FAQ) TabisColors.AccentBlue else Color.Transparent)
                        .clickable { selectedSection = SupportSection.FAQ }
                        .padding(vertical = 9.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = stringResource(R.string.tabis_support_faq_tab),
                        color = if (selectedSection == SupportSection.FAQ) Color.White else textMuted,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        if (selectedSection == SupportSection.CHAT) {
            // --- IN-APP DIRECT LIVE CHAT ---
            val isKeyboardOpen = WindowInsets.ime.getBottom(LocalDensity.current) > 0
            val bottomNavPadding = if (isKeyboardOpen || onBackClick != null) 10.dp else 94.dp
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .imePadding()
                    .padding(bottom = bottomNavPadding)
            ) {
                // Messages List Container
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .clip(TabisShapes.Card)
                        .background(cardBg)
                        .border(0.5.dp, borderColor, TabisShapes.Card)
                        .padding(horizontal = 12.dp, vertical = 8.dp)
                ) {
                    if (isLoadingMessages && messages.isEmpty()) {
                        CircularProgressIndicator(
                            color = TabisColors.AccentBlue,
                            strokeWidth = 2.dp,
                            modifier = Modifier
                                .size(28.dp)
                                .align(Alignment.Center)
                        )
                    } else if (messages.isEmpty()) {
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(24.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center
                        ) {
                            Icon(
                                painter = painterResource(R.drawable.ic_tabis_chat),
                                contentDescription = null,
                                tint = TabisColors.AccentBlue,
                                modifier = Modifier.size(40.dp)
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            Text(
                                text = stringResource(R.string.tabis_support_chat_empty),
                                color = textMuted,
                                fontSize = 13.sp,
                                lineHeight = 18.sp,
                                textAlign = TextAlign.Center
                            )
                        }
                    } else {
                        LazyColumn(
                            state = chatListState,
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                            contentPadding = PaddingValues(vertical = 8.dp)
                        ) {
                            items(messages, key = { it.id }) { msg ->
                                val isUser = msg.senderType == "user"
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth(0.82f)
                                            .clip(
                                                RoundedCornerShape(
                                                    topStart = 16.dp,
                                                    topEnd = 16.dp,
                                                    bottomStart = if (isUser) 16.dp else 4.dp,
                                                    bottomEnd = if (isUser) 4.dp else 16.dp
                                                )
                                            )
                                            .background(if (isUser) TabisColors.AccentBlue else cardSubtle)
                                            .border(
                                                width = if (isUser) 0.dp else 0.5.dp,
                                                color = borderColor,
                                                shape = RoundedCornerShape(
                                                    topStart = 16.dp,
                                                    topEnd = 16.dp,
                                                    bottomStart = if (isUser) 16.dp else 4.dp,
                                                    bottomEnd = if (isUser) 4.dp else 16.dp
                                                )
                                            )
                                            .padding(horizontal = 14.dp, vertical = 10.dp)
                                    ) {
                                        Column {
                                            if (!isUser) {
                                                Text(
                                                    text = stringResource(R.string.tabis_support_chat_admin),
                                                    color = TabisColors.AccentBlue,
                                                    fontSize = 11.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    modifier = Modifier.padding(bottom = 3.dp)
                                                )
                                            }
                                            Text(
                                                text = msg.text,
                                                color = if (isUser) Color.White else textColor,
                                                fontSize = 14.sp,
                                                lineHeight = 19.sp
                                            )
                                            if (msg.createdAt.isNotBlank()) {
                                                val timeText = msg.createdAt.substringAfter(" ").take(5)
                                                Text(
                                                    text = timeText,
                                                    color = if (isUser) Color.White.copy(alpha = 0.7f) else textDim,
                                                    fontSize = 10.sp,
                                                    modifier = Modifier
                                                        .align(Alignment.End)
                                                        .padding(top = 4.dp)
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                // Chat Input Row
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = messageInput,
                        onValueChange = { messageInput = it },
                        placeholder = {
                            Text(
                                text = stringResource(R.string.tabis_support_chat_hint),
                                color = textDim,
                                fontSize = 13.sp
                            )
                        },
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                        keyboardActions = KeyboardActions(
                            onSend = {
                                val text = messageInput.trim()
                                if (text.isNotBlank() && !isSending) {
                                    isSending = true
                                    focusManager.clearFocus()
                                    scope.launch {
                                        val (ok, _) = TabisSecurityManager.sendSupportMessage(text)
                                        if (ok) {
                                            messageInput = ""
                                            val (_, updated) = TabisSecurityManager.fetchSupportMessages()
                                            messages = updated
                                            if (updated.isNotEmpty()) {
                                                chatListState.animateScrollToItem(updated.size - 1)
                                            }
                                        } else {
                                            Toast.makeText(context, "Не удалось отправить сообщение", Toast.LENGTH_SHORT).show()
                                        }
                                        isSending = false
                                    }
                                }
                            }
                        ),
                        singleLine = false,
                        maxLines = 3,
                        shape = TabisShapes.Input,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = TabisColors.AccentBlue,
                            unfocusedBorderColor = borderColor,
                            focusedTextColor = textColor,
                            unfocusedTextColor = textColor
                        ),
                        modifier = Modifier.weight(1f)
                    )

                    Spacer(modifier = Modifier.width(8.dp))

                    Button(
                        onClick = {
                            val text = messageInput.trim()
                            if (text.isNotBlank() && !isSending) {
                                isSending = true
                                focusManager.clearFocus()
                                scope.launch {
                                    val (ok, _) = TabisSecurityManager.sendSupportMessage(text)
                                    if (ok) {
                                        messageInput = ""
                                        val (_, updated) = TabisSecurityManager.fetchSupportMessages()
                                        messages = updated
                                        if (updated.isNotEmpty()) {
                                            chatListState.animateScrollToItem(updated.size - 1)
                                        }
                                    } else {
                                        Toast.makeText(context, "Не удалось отправить сообщение", Toast.LENGTH_SHORT).show()
                                    }
                                    isSending = false
                                }
                            }
                        },
                        enabled = messageInput.isNotBlank() && !isSending,
                        shape = TabisShapes.Pill,
                        colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue),
                        modifier = Modifier.height(52.dp)
                    ) {
                        if (isSending) {
                            CircularProgressIndicator(
                                color = Color.White,
                                modifier = Modifier.size(18.dp),
                                strokeWidth = 2.dp
                            )
                        } else {
                            Text(
                                text = stringResource(R.string.tabis_support_chat_send),
                                color = Color.White,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }
        } else {
            // --- FAQ, TELEGRAM & LEGAL DOCS ---
            val faqBottomPadding = if (onBackClick != null) 24.dp else 104.dp
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(bottom = faqBottomPadding)
            ) {
                Text(
                    text = stringResource(R.string.tabis_support_subtitle),
                    color = textMuted,
                    fontSize = 13.sp,
                    lineHeight = 18.sp
                )

                Spacer(modifier = Modifier.height(18.dp))

                // Telegram Action Card
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
                                    .size(44.dp)
                                    .clip(CircleShape)
                                    .background(TabisColors.AccentBlueBg),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    painter = painterResource(R.drawable.ic_tabis_chat),
                                    contentDescription = null,
                                    tint = TabisColors.AccentBlue,
                                    modifier = Modifier.size(22.dp)
                                )
                            }

                            Spacer(modifier = Modifier.width(14.dp))

                            Column {
                                Text(
                                    text = stringResource(R.string.tabis_support_telegram_btn),
                                    color = textColor,
                                    fontSize = 16.sp,
                                    fontWeight = FontWeight.SemiBold
                                )
                                Text(
                                    text = stringResource(R.string.tabis_support_telegram_desc),
                                    color = textMuted,
                                    fontSize = 12.sp,
                                    modifier = Modifier.padding(top = 2.dp)
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(18.dp))

                        Button(
                            onClick = {
                                try {
                                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://t.me/tabisvpn"))
                                    context.startActivity(intent)
                                } catch (_: Exception) {}
                            },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(50.dp),
                            shape = TabisShapes.Pill,
                            colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                        ) {
                            Text(
                                text = "Перейти в Telegram-канал (@tabisvpn)",
                                color = Color.White,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(24.dp))

                // FAQ Section
                Text(
                    text = stringResource(R.string.tabis_support_faq_title),
                    color = textDim,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp,
                    letterSpacing = 1.sp,
                    modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                )

                FaqAccordionItem(
                    question = stringResource(R.string.tabis_support_faq1_q),
                    answer = stringResource(R.string.tabis_support_faq1_a),
                    isDarkTheme = isDarkTheme
                )

                Spacer(modifier = Modifier.height(8.dp))

                FaqAccordionItem(
                    question = stringResource(R.string.tabis_support_faq2_q),
                    answer = stringResource(R.string.tabis_support_faq2_a),
                    isDarkTheme = isDarkTheme
                )

                Spacer(modifier = Modifier.height(8.dp))

                FaqAccordionItem(
                    question = stringResource(R.string.tabis_support_faq3_q),
                    answer = stringResource(R.string.tabis_support_faq3_a),
                    isDarkTheme = isDarkTheme
                )

                Spacer(modifier = Modifier.height(24.dp))

                // Legal Documents Section
                Text(
                    text = stringResource(R.string.tabis_legal_section_docs),
                    color = textDim,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp,
                    letterSpacing = 1.sp,
                    modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
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
            }
        }
    }
}

@Composable
private fun FaqAccordionItem(
    question: String,
    answer: String,
    isDarkTheme: Boolean
) {
    var expanded by remember { mutableStateOf(false) }
    val textColor = if (isDarkTheme) TabisColors.DarkText else TabisColors.LightText
    val textMuted = if (isDarkTheme) TabisColors.DarkTextMuted else TabisColors.LightTextMuted
    val cardBg = if (isDarkTheme) TabisColors.DarkCard else TabisColors.LightCard
    val borderColor = if (isDarkTheme) TabisColors.DarkBorder else TabisColors.LightBorder

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(TabisShapes.InnerCard)
            .background(cardBg)
            .border(0.5.dp, borderColor, TabisShapes.InnerCard)
            .clickable { expanded = !expanded }
            .padding(16.dp)
    ) {
        Column {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = question,
                    color = textColor,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.weight(1f)
                )
                Text(
                    text = if (expanded) "−" else "+",
                    color = TabisColors.AccentBlue,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(start = 8.dp)
                )
            }

            AnimatedVisibility(visible = expanded) {
                Text(
                    text = answer,
                    color = textMuted,
                    fontSize = 12.sp,
                    lineHeight = 17.sp,
                    modifier = Modifier.padding(top = 10.dp)
                )
            }
        }
    }
}
