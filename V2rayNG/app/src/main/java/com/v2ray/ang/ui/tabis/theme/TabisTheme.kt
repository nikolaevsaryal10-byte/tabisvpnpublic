package com.v2ray.ang.ui.tabis.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

object TabisShapes {
    val CardRadius = 24.dp
    val InnerCardRadius = 18.dp
    val InputRadius = 16.dp
    val PillRadius = 32.dp
    val BadgeRadius = 10.dp

    val Card = RoundedCornerShape(CardRadius)
    val InnerCard = RoundedCornerShape(InnerCardRadius)
    val Input = RoundedCornerShape(InputRadius)
    val Pill = RoundedCornerShape(PillRadius)
    val Badge = RoundedCornerShape(BadgeRadius)
}

object TabisColors {
    val AccentBlue = Color(0xFF089AFF)
    val AccentBlueBg = Color(0x1F089AFF) // ~12% opacity
    val ConnectedGreen = Color(0xFF10B981)
    val DisconnectedRed = Color(0xFFEF4444)

    // Dark Mode (Buro style)
    val DarkBg = Color(0xFF0D0F11)
    val DarkCard = Color(0xFF15181C)
    val DarkCardSubtle = Color(0xFF1C1F24)
    val DarkBorder = Color(0xFF22252A)
    val DarkText = Color(0xFFF4F5F6)
    val DarkTextMuted = Color(0xFF8A8F98)
    val DarkTextDim = Color(0xFF5C626C)
    val DarkNavBg = Color(0xEE15181C)
    val DarkBadgeBg = Color(0xFF1C2025)

    // Light Mode (Buro style)
    val LightBg = Color(0xFFFCFCFA)
    val LightCard = Color(0xFFFFFFFF)
    val LightCardSubtle = Color(0xFFF6F7F8)
    val LightBorder = Color(0xFFE7E8EA)
    val LightText = Color(0xFF101112)
    val LightTextMuted = Color(0xFF70757D)
    val LightTextDim = Color(0xFFA0A5AD)
    val LightNavBg = Color(0xEEFFFFFF)
    val LightBadgeBg = Color(0xFFF1F3F5)
}

private val TabisDarkColorScheme = darkColorScheme(
    primary = TabisColors.AccentBlue,
    onPrimary = Color.White,
    primaryContainer = TabisColors.DarkCardSubtle,
    onPrimaryContainer = TabisColors.DarkText,
    secondary = TabisColors.AccentBlue,
    onSecondary = Color.White,
    background = TabisColors.DarkBg,
    onBackground = TabisColors.DarkText,
    surface = TabisColors.DarkCard,
    onSurface = TabisColors.DarkText,
    surfaceVariant = TabisColors.DarkCardSubtle,
    onSurfaceVariant = TabisColors.DarkTextMuted,
    outline = TabisColors.DarkBorder,
)

private val TabisLightColorScheme = lightColorScheme(
    primary = TabisColors.AccentBlue,
    onPrimary = Color.White,
    primaryContainer = TabisColors.LightCardSubtle,
    onPrimaryContainer = TabisColors.LightText,
    secondary = TabisColors.AccentBlue,
    onSecondary = Color.White,
    background = TabisColors.LightBg,
    onBackground = TabisColors.LightText,
    surface = TabisColors.LightCard,
    onSurface = TabisColors.LightText,
    surfaceVariant = TabisColors.LightCardSubtle,
    onSurfaceVariant = TabisColors.LightTextMuted,
    outline = TabisColors.LightBorder,
)

@Composable
fun TabisTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) TabisDarkColorScheme else TabisLightColorScheme

    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}
