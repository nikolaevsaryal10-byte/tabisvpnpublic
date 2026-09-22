package com.v2ray.ang.ui.tabis

import com.v2ray.ang.fmt.VlessFmt
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class TabisSecurityManagerTest {

    @Test
    fun testEncryptionRoundTrip() {
        val sample = "vless://00000000-0000-0000-0000-000000000000@127.0.0.1:443?security=reality&sni=example.com#test"
        val encrypted = TabisSecurityManager.encrypt(sample)
        assertNotNull("Encrypted string must not be null", encrypted)

        val decrypted = TabisSecurityManager.decrypt(encrypted!!)
        assertEquals(sample, decrypted)

        val profile = VlessFmt.parse(decrypted!!)
        assertNotNull("Profile parsing must not return null", profile)
        assertEquals("127.0.0.1", profile?.server)
        assertEquals("443", profile?.serverPort)
    }
}
