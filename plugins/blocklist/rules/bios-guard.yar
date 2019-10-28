rule IntelBiosGuard
{
    meta:
        license = "GPL-2.0+"
        description = "Contains Intel BIOS Guard"
        long_description = "Hardware-assisted authentication and protection against BIOS recovery attacks"
        fail = false
        claim = "success-bios-guard"

    strings:
        $signature = "_AMIPFAT"
        $updater = "AmiFlashUpd" wide
        $header = "__BGKH__"

    condition:
       $header or ($signature and not $updater)
}
