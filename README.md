Linux Vendor Firmware Service
=============================

This is the website for the Linux Vendor Firmware Service

Missing firmware at LVFS
------------------------

If your device is missing a firmware update that you think should be on LVFS
please file an issue against this project and apply the Github label *missing-firmware*.

Setting up the web service
--------------------------

The official instance is set up using puppet on RHEL 7, on which you could use:

    yum-config-manager --add-repo https://copr.fedorainfracloud.org/coprs/rhughes/lvfs-website/repo/epel-7/rhughes-lvfs-website-epel-7.repo
    yum install epel-release libgcab1 puppet
    git clone https://github.com/hughsie/lvfs-puppet.git
    cd lvfs-puppet
    hostname admin
    puppet module install puppetlabs-vcsrepo --version 2.2.0
    cp keys.pp.in keys.pp
    vim keys.pp
    puppet apply .

You can set up the development database manually using:

    $ psql -u root
    > CREATE DATABASE lvfs;
    > CREATE USER 'test'@'localhost' IDENTIFIED BY 'test';
    > USE lvfs;
    > GRANT ALL ON lvfs.* TO 'test'@'localhost';
    > exit

Then create the schema using:

    FLASK_APP=lvfs/__init__.py flask-3 initdb
    FLASK_APP=lvfs/__init__.py flask-3 db stamp
    FLASK_APP=lvfs/__init__.py flask-3 db upgrade

The admin user is set as `sign-test@fwupd.org` with password `Pa$$w0rd`.

## Running locally ##

    python3 -m virtualenv env
    source env/bin/activate
    pip3 install -r requirements.txt
    FLASK_DEBUG=1 ./app.wsgi

You may also need to install introspection dependencies.

For example on Ubuntu the following is required:

    sudo apt install -y python3-gi gcab gir1.2-libgcab-1.0

On Fedora:

    sudo dnf install \
        bsdtar \
        cairo-gobject-devel \
        GeoIP-devel \
        gnutls-utils \
        gobject-introspection-devel \
        postgresql-server \
        python36-pip \
        python36-psutil \
        python36-virtualenv

## Generating a SSL certificate ##

IMPORTANT: The LVFS needs to be hosted over SSL.
If you want to use LetsEncrypt you can just do `certbot --nginx`.

## Installing the test key ##

Use the test GPG key (with the initial password of `fwupd`).

    gpg2 --homedir=/var/www/lvfs/.gnupg --allow-secret-key-import --import /var/www/lvfs/stable/contrib/fwupd-test-private.key
    gpg2 --homedir=/var/www/lvfs/.gnupg --list-secret-keys
    gpg2 --homedir=/var/www/lvfs/.gnupg --edit-key D64F5C21
    gpg> passwd
    gpg> trust
    gpg> quit

If passwd cannot be run due to being in a sudo session you can do:

    gpg-agent --homedir=/var/www/lvfs/.gnupg --daemon

or

    script /dev/null
    gpg2...

## Using the production key ##

Use the secure GPG key (with the long secret password).

    cd
    gpg2 --homedir=/var/www/lvfs/.gnupg --allow-secret-key-import --import fwupd-secret-signing-key.key
    gpg2 --homedir=/var/www/lvfs/.gnupg --list-secret-keys
    gpg2 --homedir=/var/www/lvfs/.gnupg --edit-key 4538BAC2
      gpg> passwd
      gpg> quit

## Generating metadata for pre-signed firmware ##

If the firmware is already signed with a PKCS-7 or GPG signature and is going
to be shipped out-of-band from the usual LVFS workflow then `local.py` can be
used to generate metadata for `/usr/share/fwupd/remotes.d/vendor/firmware/`.

An example of generating metadata:
```
./local.py --archive-directory /usr/share/fwupd/remotes.d/vendor/ --basename firmware --metadata /usr/share/fwupd/remotes.d/vendor/vendor.xml.gz
```

This assumes that the firmware CAB files are already in `/usr/share/fwupd/remotes.d/vendor/firmware`
and will be run on that system.
