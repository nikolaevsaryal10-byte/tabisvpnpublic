package com.v2ray.ang.ui.tabis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.Locale

class TabisUpdateManagerTest {

    // --- Tests for calculateSha256 ---

    @Test
    fun testCalculateSha256EmptyFile() {
        val tempFile = File.createTempFile("test_sha256_empty_", ".tmp")
        try {
            // Empty file
            val expectedHash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            val actualHash = TabisUpdateManager.calculateSha256(tempFile)
            assertEquals(expectedHash, actualHash)
        } finally {
            tempFile.delete()
        }
    }

    @Test
    fun testCalculateSha256KnownTestVectors() {
        // NIST test vector: "abc"
        val tempFileAbc = File.createTempFile("test_sha256_abc_", ".tmp")
        try {
            tempFileAbc.writeText("abc", Charsets.UTF_8)
            val expectedAbc = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
            val actualAbc = TabisUpdateManager.calculateSha256(tempFileAbc)
            assertEquals(expectedAbc, actualAbc)
        } finally {
            tempFileAbc.delete()
        }

        // Test vector: "hello world"
        val tempFileHw = File.createTempFile("test_sha256_hw_", ".tmp")
        try {
            tempFileHw.writeText("hello world", Charsets.UTF_8)
            val expectedHw = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
            val actualHw = TabisUpdateManager.calculateSha256(tempFileHw)
            assertEquals(expectedHw, actualHw)
        } finally {
            tempFileHw.delete()
        }
    }

    @Test
    fun testCalculateSha256StreamingMultiBuffer() {
        // Create 20KB test payload exceeding the 8192-byte internal buffer
        val size = 20480
        val payload = ByteArray(size) { i -> (i % 256).toByte() }

        val digest = MessageDigest.getInstance("SHA-256")
        digest.update(payload)
        val hashBytes = digest.digest()
        val expectedHash = hashBytes.joinToString("") { "%02x".format(Locale.US, it) }

        val tempFile = File.createTempFile("test_sha256_multi_", ".tmp")
        try {
            FileOutputStream(tempFile).use { fos ->
                fos.write(payload)
                fos.flush()
            }
            val actualHash = TabisUpdateManager.calculateSha256(tempFile)
            assertEquals(expectedHash, actualHash)
        } finally {
            tempFile.delete()
        }
    }

    // --- Tests for areSignaturesMatching ---

    @Test
    fun testAreSignaturesMatchingSingleCertMatch() {
        val certA = byteArrayOf(0x30, 0x82.toByte(), 0x01, 0x0A, 0x55, 0xAA.toByte())
        val currentSignatures = listOf(certA)
        val apkSignatures = listOf(certA.clone())

        assertTrue(
            "Identical single certificate must match",
            TabisUpdateManager.areSignaturesMatching(currentSignatures, apkSignatures)
        )
    }

    @Test
    fun testAreSignaturesMatchingSingleCertMismatch() {
        val certA = byteArrayOf(0x30, 0x82.toByte(), 0x01, 0x0A)
        val certB = byteArrayOf(0x30, 0x82.toByte(), 0x01, 0x0B)
        val currentSignatures = listOf(certA)
        val apkSignatures = listOf(certB)

        assertFalse(
            "Mismatched single certificate must not match",
            TabisUpdateManager.areSignaturesMatching(currentSignatures, apkSignatures)
        )
    }

    @Test
    fun testAreSignaturesMatchingMultiCertSameOrder() {
        val certA = byteArrayOf(0x10, 0x20, 0x30)
        val certB = byteArrayOf(0x40, 0x50, 0x60)
        val currentSignatures = listOf(certA, certB)
        val apkSignatures = listOf(certA.clone(), certB.clone())

        assertTrue(
            "Identical multi-signer certificates in same order must match",
            TabisUpdateManager.areSignaturesMatching(currentSignatures, apkSignatures)
        )
    }

    @Test
    fun testAreSignaturesMatchingMultiCertReordered() {
        val certA = byteArrayOf(0x10, 0x20, 0x30)
        val certB = byteArrayOf(0x40, 0x50, 0x60)
        val currentSignatures = listOf(certA, certB)
        val apkSignatures = listOf(certB.clone(), certA.clone())

        assertTrue(
            "Identical multi-signer certificates in reordered sequence must match (set equality)",
            TabisUpdateManager.areSignaturesMatching(currentSignatures, apkSignatures)
        )
    }

    @Test
    fun testAreSignaturesMatchingSecondaryCertTampered() {
        // Adversarial scenario: KeyA matches, but secondary signer KeyB was replaced with malicious key
        val certA = byteArrayOf(0x10, 0x20, 0x30)
        val certB = byteArrayOf(0x40, 0x50, 0x60)
        val certMalicious = byteArrayOf(0x66, 0x66, 0x66)
        val currentSignatures = listOf(certA, certB)
        val apkSignatures = listOf(certA.clone(), certMalicious)

        assertFalse(
            "Tampered secondary certificate must be rejected even if first certificate matches",
            TabisUpdateManager.areSignaturesMatching(currentSignatures, apkSignatures)
        )
    }

    @Test
    fun testAreSignaturesMatchingStrippedCert() {
        // Adversarial scenario: Multi-signer app stripped of secondary certificate
        val certA = byteArrayOf(0x10, 0x20, 0x30)
        val certB = byteArrayOf(0x40, 0x50, 0x60)
        val currentSignatures = listOf(certA, certB)
        val apkSignatures = listOf(certA.clone())

        assertFalse(
            "Stripped certificate signature list must be rejected due to size mismatch",
            TabisUpdateManager.areSignaturesMatching(currentSignatures, apkSignatures)
        )
    }

    @Test
    fun testAreSignaturesMatchingAddedCert() {
        val certA = byteArrayOf(0x10, 0x20, 0x30)
        val certB = byteArrayOf(0x40, 0x50, 0x60)
        val currentSignatures = listOf(certA)
        val apkSignatures = listOf(certA.clone(), certB)

        assertFalse(
            "Signature list with extra certificate must be rejected",
            TabisUpdateManager.areSignaturesMatching(currentSignatures, apkSignatures)
        )
    }

    @Test
    fun testAreSignaturesMatchingEmptyLists() {
        val certA = byteArrayOf(0x10, 0x20, 0x30)

        assertFalse(
            "Both empty lists must be rejected",
            TabisUpdateManager.areSignaturesMatching(emptyList(), emptyList())
        )
        assertFalse(
            "Empty APK signatures list must be rejected",
            TabisUpdateManager.areSignaturesMatching(listOf(certA), emptyList())
        )
        assertFalse(
            "Empty current signatures list must be rejected",
            TabisUpdateManager.areSignaturesMatching(emptyList(), listOf(certA))
        )
    }

    @Test
    fun testAreSignaturesMatchingDuplicateCertsMismatchedCounts() {
        val certA = byteArrayOf(0x10, 0x20, 0x30)
        val certB = byteArrayOf(0x40, 0x50, 0x60)

        // Same size (2), but apk has [A, A] while current has [A, B]
        val currentSignatures = listOf(certA, certB)
        val apkSignatures = listOf(certA.clone(), certA.clone())

        assertFalse(
            "Duplicate cert substitution must be rejected",
            TabisUpdateManager.areSignaturesMatching(currentSignatures, apkSignatures)
        )
    }

    @Test
    fun testAreSignaturesMatchingMultisetMultiplicityMismatch() {
        // App signed with [Cert1, Cert1, Cert2]; APK signed with [Cert1, Cert2, Cert2] -> MUST BE REJECTED
        val cert1 = byteArrayOf(0x10, 0x20, 0x30)
        val cert2 = byteArrayOf(0x40, 0x50, 0x60)

        val currentSignatures = listOf(cert1, cert1.clone(), cert2)
        val apkSignatures = listOf(cert1.clone(), cert2, cert2.clone())

        assertFalse(
            "Multiset multiplicity mismatch [Cert1, Cert1, Cert2] vs [Cert1, Cert2, Cert2] must be rejected",
            TabisUpdateManager.areSignaturesMatching(currentSignatures, apkSignatures)
        )

        assertFalse(
            "Inverse multiset multiplicity mismatch [Cert1, Cert2, Cert2] vs [Cert1, Cert1, Cert2] must be rejected",
            TabisUpdateManager.areSignaturesMatching(apkSignatures, currentSignatures)
        )
    }

    @Test
    fun testAreSignaturesMatchingMultisetMultiplicityMatchPermuted() {
        // App signed with [Cert1, Cert2, Cert1]; APK signed with [Cert1, Cert1, Cert2] -> MUST PASS (multisets match)
        val cert1 = byteArrayOf(0x10, 0x20, 0x30)
        val cert2 = byteArrayOf(0x40, 0x50, 0x60)

        val currentSignatures = listOf(cert1, cert2, cert1.clone())
        val apkSignatures = listOf(cert1.clone(), cert1.clone(), cert2)

        assertTrue(
            "Permuted multisets with matching multiplicities [Cert1, Cert2, Cert1] vs [Cert1, Cert1, Cert2] must pass",
            TabisUpdateManager.areSignaturesMatching(currentSignatures, apkSignatures)
        )
    }
}
