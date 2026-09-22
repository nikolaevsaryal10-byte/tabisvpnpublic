package com.v2ray.ang.ui.tabis

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.v2ray.ang.R
import com.v2ray.ang.ui.tabis.theme.TabisColors
import com.v2ray.ang.ui.tabis.theme.TabisShapes

enum class TabisLegalDocType {
    TERMS,
    PRIVACY
}

data class TabisLegalSection(
    val title: String,
    val items: List<String>
)

@Composable
fun TabisLegalDocDialog(
    docType: TabisLegalDocType,
    isDarkTheme: Boolean,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val textColor = if (isDarkTheme) TabisColors.DarkText else TabisColors.LightText
    val textMuted = if (isDarkTheme) TabisColors.DarkTextMuted else TabisColors.LightTextMuted
    val textDim = if (isDarkTheme) TabisColors.DarkTextDim else TabisColors.LightTextDim
    val cardBg = if (isDarkTheme) TabisColors.DarkCard else TabisColors.LightCard
    val cardSubtle = if (isDarkTheme) TabisColors.DarkCardSubtle else TabisColors.LightCardSubtle
    val borderColor = if (isDarkTheme) TabisColors.DarkBorder else TabisColors.LightBorder

    val isTerms = docType == TabisLegalDocType.TERMS
    val docTitle = stringResource(if (isTerms) R.string.tabis_legal_title_terms else R.string.tabis_legal_title_privacy)
    val webUrl = if (isTerms) "https://tabisvpn.site/terms.html" else "https://tabisvpn.site/privacy.html"
    val sections = if (isTerms) getTermsSections() else getPrivacySections()

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.65f))
                .clickable(onClick = onDismiss),
            contentAlignment = Alignment.Center
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(0.92f)
                    .fillMaxHeight(0.86f)
                    .clip(TabisShapes.Card)
                    .background(cardBg)
                    .border(0.5.dp, borderColor, TabisShapes.Card)
                    .clickable(enabled = false) {}
                    .padding(20.dp)
            ) {
                Column(modifier = Modifier.fillMaxSize()) {
                    // Header: Title and Close button
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = docTitle,
                                color = textColor,
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = stringResource(R.string.tabis_legal_version_subtitle),
                                color = textDim,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 10.sp,
                                letterSpacing = 0.5.sp,
                                modifier = Modifier.padding(top = 2.dp)
                            )
                        }

                        IconButton(
                            onClick = onDismiss,
                            modifier = Modifier
                                .size(36.dp)
                                .clip(CircleShape)
                                .background(cardSubtle)
                        ) {
                            Text(
                                text = "✕",
                                color = textMuted,
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))
                    Box(modifier = Modifier.fillMaxWidth().height(0.5.dp).background(borderColor))
                    Spacer(modifier = Modifier.height(12.dp))

                    // Scrollable content
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .verticalScroll(rememberScrollState())
                    ) {
                        sections.forEachIndexed { index, section ->
                            Text(
                                text = section.title,
                                color = TabisColors.AccentBlue,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(bottom = 6.dp, top = if (index > 0) 14.dp else 0.dp)
                            )
                            section.items.forEach { item ->
                                Text(
                                    text = item,
                                    color = textMuted,
                                    fontSize = 12.sp,
                                    lineHeight = 17.sp,
                                    modifier = Modifier.padding(bottom = 6.dp)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))
                    Box(modifier = Modifier.fillMaxWidth().height(0.5.dp).background(borderColor))
                    Spacer(modifier = Modifier.height(12.dp))

                    // Footer actions
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedButton(
                            onClick = {
                                try {
                                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(webUrl))
                                    context.startActivity(intent)
                                } catch (_: Exception) {}
                            },
                            modifier = Modifier
                                .weight(1f)
                                .height(46.dp),
                            shape = TabisShapes.Pill,
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = TabisColors.AccentBlue)
                        ) {
                            Text(
                                text = stringResource(R.string.tabis_legal_open_browser),
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Medium
                            )
                        }

                        Button(
                            onClick = onDismiss,
                            modifier = Modifier
                                .weight(1f)
                                .height(46.dp),
                            shape = TabisShapes.Pill,
                            colors = ButtonDefaults.buttonColors(containerColor = TabisColors.AccentBlue)
                        ) {
                            Text(
                                text = stringResource(R.string.tabis_legal_close),
                                color = Color.White,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }
            }
        }
    }
}

private fun getTermsSections(): List<TabisLegalSection> = listOf(
    TabisLegalSection(
        title = "Публичная оферта и акцепт (ст. 437, 438 ГК РФ)",
        items = listOf(
            "Настоящий документ является официальным публичным предложением Исполнителя — Николаева Сарыала Павловича (ИНН 141702115563) любому дееспособному физическому или юридическому лицу.",
            "Факт оплаты доступа, активации цифрового ключа или использования ПО Сервиса является полным и безоговорочным принятием всех условий настоящего Соглашения без каких-либо изъятий или ограничений."
        )
    ),
    TabisLegalSection(
        title = "1. Термины и определения",
        items = listOf(
            "• Сервис Tabis VPN — совокупность программного обеспечения, вычислительных мощностей, сетевых шлюзов и зашифрованных каналов связи, администрируемых Исполнителем.",
            "• Ключ доступа (Токен) — уникальная цифровая криптографическая последовательность для авторизации и защищенного туннелирования.",
            "• Личный кабинет — веб-интерфейс на сайте tabisvpn.site для управления подпиской, ключами и устройствами."
        )
    ),
    TabisLegalSection(
        title = "2. Предмет соглашения и назначение",
        items = listOf(
            "2.1. Исполнитель предоставляет право использования программной инфраструктуры Tabis VPN для организации сквозного криптографического туннелирования трафика, а Пользователь обязуется оплачивать доступ по выбранному тарифу.",
            "2.2. Специальное назначение: защита данных от перехвата в незащищенных сетях (включая публичные Wi-Fi), предотвращение MITM-атак, целостность и шифрование пакетов, сетевая оптимизация и снижение пинга.",
            "2.3. Сервис не создавался и не позиционируется как средство для обхода установленных в законном порядке ограничений доступа к информации."
        )
    ),
    TabisLegalSection(
        title = "3. Правила допустимого использования (AUP)",
        items = listOf(
            "3.1. Пользователь обязуется использовать Сервис исключительно в законных целях с соблюдением законодательства РФ и страны своего нахождения.",
            "3.2. Категорически запрещены: сетевые атаки (DDoS, DoS, сканирование портов, брутфорс, IP-spoofing), распространение вредоносного ПО и эксплойтов, массовые рассылки (СПАМ), фишинг, несанкционированный доступ к чужим системам, распространение экстремистских и запрещенных материалов.",
            "3.3. При фиксации нарушений или жалоб от дата-центров доступ блокируется немедленно в одностороннем порядке без возврата средств."
        )
    ),
    TabisLegalSection(
        title = "4. Оплата, доставка и возврат средств",
        items = listOf(
            "4.1. Доступ предоставляется на условиях 100% предоплаты через платежный шлюз ЮKassa (банковские карты МИР, Visa, Mastercard РФ, СБП). Безопасность гарантируется протоколами TLS и 3-D Secure.",
            "4.2. Цифровой ключ активируется мгновенно в автоматическом режиме сразу после подтверждения транзакции.",
            "4.3. В соответствии со ст. 32 Закона РФ «О защите прав потребителей» и ст. 782 ГК РФ Пользователь вправе в любое время отказаться от услуг с возвратом денежных средств за неиспользованные дни доступа за вычетом документально подтвержденных фактически понесенных расходов Исполнителя. Срок рассмотрения заявления и перечисления средств — до 10 календарных дней."
        )
    ),
    TabisLegalSection(
        title = "5. Ответственность сторон",
        items = listOf(
            "5.1. Услуги предоставляются по принципу «как есть» (as is). Исполнитель стремится к обеспечению максимальной надежности и доступности шлюзов.",
            "5.2. Исполнитель не несет ответственности за сбои на стороне интернет-провайдеров пользователя, магистральных операторов связи или обстоятельства непреодолимой силы."
        )
    ),
    TabisLegalSection(
        title = "6. Реквизиты Исполнителя",
        items = listOf(
            "Исполнитель: Николаев Сарыал Павлович",
            "ИНН: 141702115563",
            "Электронная почта: support@tabisvpn.site",
            "Telegram-канал: @tabisvpn (https://t.me/tabisvpn)",
            "Официальный веб-сайт: https://tabisvpn.site"
        )
    )
)

private fun getPrivacySections(): List<TabisLegalSection> = listOf(
    TabisLegalSection(
        title = "1. Общие положения и соответствие 152-ФЗ",
        items = listOf(
            "Настоящая Политика конфиденциальности определяет порядок обработки информации сервисом Tabis VPN с учетом требований Федерального закона РФ от 27.07.2006 № 152-ФЗ «О персональных данных» и мировых стандартов Privacy by Design.",
            "Главный приоритет сервиса Tabis VPN — защита конфиденциальности, целостность сетевого трафика и надежное сквозное шифрование."
        )
    ),
    TabisLegalSection(
        title = "2. Обезличенный статус данных (Non-PII)",
        items = listOf(
            "2.1. Сервис не осуществляет сбор персональных данных в смысле ст. 3 Федерального закона № 152-ФЗ.",
            "2.2. Сервис не запрашивает и не сохраняет паспортные данные, номера телефонов, адреса проживания и реквизиты банковских карт Пользователей.",
            "2.3. Вся техническая информация обрабатывается в автоматическом режиме и строго обезличена."
        )
    ),
    TabisLegalSection(
        title = "3. Принцип минимального журналирования",
        items = listOf(
            "3.1. Сетевой транзитный контур: Сервис НЕ ведет журналы посещенных ресурсов, НЕ сохраняет URL-адреса, НЕ просматривает и не сохраняет полезную нагрузку трафика, переписку и DNS-запросы.",
            "3.2. Управляющий биллинговый контур: фиксируется только связка «обезличенный токен ↔ временные метки сессии» и счетчик объема переданного трафика для контроля квот выбранного тарифа."
        )
    ),
    TabisLegalSection(
        title = "4. Категории обрабатываемых данных",
        items = listOf(
            "• Уникальный ключ (токен) доступа — для проверки активной подписки и авторизации на сетевом шлюзе.",
            "• Агрегированный объем трафика (ГБ) — для контроля квот тарифа (обнуляется в начале каждого календарного месяца).",
            "• Адрес электронной почты аккаунта — исключительно для входа в Личный кабинет и доставки разовых кодов верификации."
        )
    ),
    TabisLegalSection(
        title = "5. Безопасность и хранение данных",
        items = listOf(
            "5.1. Все соединения между устройствами пользователя и шлюзами шифруются современными стойкими протоколами (Hysteria 2 / TLS 1.3).",
            "5.2. Доступ к вычислительным узлам изолирован и защищен криптографическими ключами с разграничением прав доступа."
        )
    ),
    TabisLegalSection(
        title = "6. Контакты службы поддержки",
        items = listOf(
            "По всем вопросам относительно политики конфиденциальности:",
            "Электронная почта: support@tabisvpn.site",
            "Telegram-канал: @tabisvpn (https://t.me/tabisvpn)",
            "Страница на сайте: https://tabisvpn.site/privacy.html"
        )
    )
)
