rule IntelBootGuard
{
    meta:
        license = "GPL-2.0+"
        description = "Contains Intel Boot Guard"
        long_description = "Protection against boot block-level malware and provides an added level of hardware-based platform security"
        fail = false
        claim = "success-boot-guard"

    strings:
        $boot_policy_manifest_header = "__ACBP__"
        $ibb_element = "__IBBS__"

    condition:
       all of them
}
