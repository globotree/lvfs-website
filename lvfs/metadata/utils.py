#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: GPL-2.0+
#
# pylint: disable=too-many-statements,too-many-locals,too-many-nested-blocks

import os
import hashlib

from collections import defaultdict
from lxml import etree as ET

from lvfs import app, db

from lvfs.models import Firmware, Remote
from lvfs.util import _get_settings, _xml_from_markdown

def _generate_metadata_kind(filename, fws, firmware_baseuri='', local=False):
    """ Generates AppStream metadata of a specific kind """

    root = ET.Element('components')
    root.set('origin', 'lvfs')
    root.set('version', '0.9')

    # build a map of appstream_id:mds
    components = defaultdict(list)
    for fw in sorted(fws, key=lambda fw: fw.mds[0].appstream_id):
        for md in fw.mds:
            components[md.appstream_id].append(md)

    # process each component in version order, but only include the latest 5
    # releases to keep the metadata size sane
    for appstream_id in sorted(components):
        mds = sorted(components[appstream_id], reverse=True)[:5]
        # assume all the components have the same parent firmware information
        md = mds[0]
        component = ET.SubElement(root, 'component')
        component.set('type', 'firmware')
        ET.SubElement(component, 'id').text = md.appstream_id
        # until all front ends support <category> and <name_variant_suffix> append both */
        ET.SubElement(component, 'name').text = md.name_with_category
        #ET.SubElement(component, 'name_variant_suffix').text = md.name_variant_suffix
        ET.SubElement(component, 'summary').text = md.summary
        ET.SubElement(component, 'developer_name').text = md.developer_name
        if md.description:
            component.append(_xml_from_markdown(md.description))
        ET.SubElement(component, 'project_license').text = md.project_license
        if md.url_homepage:
            child = ET.SubElement(component, 'url')
            child.set('type', 'homepage')
            child.text = md.url_homepage
        for md in mds:
            if md.priority:
                component.set('priority', str(md.priority))

        # add requires for each allowed vendor_ids
        elements = {}
        for md in mds:
            if local:
                break

            # the vendor can upload to any hardware
            vendor = md.fw.vendor_odm
            if vendor.is_unrestricted:
                continue

            # no restrictions in place!
            if not vendor.restrictions:
                child = ET.Element('firmware')
                child.text = 'vendor-id'
                child.set('compare', 'eq')
                child.set('version', 'XXX:NEVER_GOING_TO_MATCH')
                elements['vendor-id'] = child
                continue

            # allow specifying more than one ID
            vendor_ids = [res.value for res in vendor.restrictions]
            child = ET.Element('firmware')
            child.text = 'vendor-id'
            if len(vendor_ids) == 1:
                child.set('compare', 'eq')
            else:
                child.set('compare', 'regex')
            child.set('version', '|'.join(vendor_ids))
            elements['vendor-id'] = child

        # add requires for <firmware> or fwupd version
        for md in mds:
            for rq in md.requirements:
                if rq.kind == 'hardware':
                    continue
                child = ET.Element(rq.kind)
                if rq.value:
                    child.text = rq.value
                if rq.compare:
                    child.set('compare', rq.compare)
                if rq.version:
                    child.set('version', rq.version)
                if rq.depth:
                    child.set('depth', rq.depth)
                elements[rq.kind + str(rq.value)] = child

        # add a single requirement for <hardware>
        rq_hws = []
        for md in mds:
            for rq in md.requirements:
                if rq.kind == 'hardware' and rq.value not in rq_hws:
                    rq_hws.append(rq.value)
        if rq_hws:
            child = ET.Element('hardware')
            child.text = '|'.join(rq_hws)
            elements['hardware'] = child

        # requires shared by all releases
        if elements:
            parent = ET.SubElement(component, 'requires')
            for key in elements:
                parent.append(elements[key])

        # screenshot shared by all releases
        elements = {}
        for md in mds:
            if not md.screenshot_url and not md.screenshot_caption:
                continue
            # try to dedupe using the URL and then the caption
            key = md.screenshot_url
            if not key:
                key = md.screenshot_caption
            if key not in elements:
                child = ET.Element('screenshot')
                if not elements:
                    child.set('type', 'default')
                if md.screenshot_caption:
                    ET.SubElement(child, 'caption').text = md.screenshot_caption
                if md.screenshot_url:
                    ET.SubElement(child, 'image').text = md.screenshot_url
                elements[key] = child
        if elements:
            parent = ET.SubElement(component, 'screenshots')
            for key in elements:
                parent.append(elements[key])

        # add each release
        releases = ET.SubElement(component, 'releases')
        for md in mds:
            if not md.version:
                continue
            rel = ET.SubElement(releases, 'release')
            if md.release_timestamp:
                rel.set('timestamp', str(md.release_timestamp))
            if md.release_urgency and md.release_urgency != 'unknown':
                rel.set('urgency', md.release_urgency)
            if md.version:
                rel.set('version', md.version)
            ET.SubElement(rel, 'location').text = firmware_baseuri + md.fw.filename

            # add container checksum
            if md.fw.checksum_signed_sha1 or local:
                csum = ET.SubElement(rel, 'checksum')
                #metadata intended to be used locally won't be signed
                if local:
                    csum.text = md.fw.checksum_upload_sha1
                else:
                    csum.text = md.fw.checksum_signed_sha1
                csum.set('type', 'sha1')
                csum.set('filename', md.fw.filename)
                csum.set('target', 'container')
            if md.fw.checksum_signed_sha256 or local:
                csum = ET.SubElement(rel, 'checksum')
                if local:
                    csum.text = md.fw.checksum_upload_sha256
                else:
                    csum.text = md.fw.checksum_signed_sha256
                csum.set('type', 'sha256')
                csum.set('filename', md.fw.filename)
                csum.set('target', 'container')

            # add content checksum
            if md.checksum_contents:
                csum = ET.SubElement(rel, 'checksum')
                csum.text = md.checksum_contents
                csum.set('type', 'sha1')
                csum.set('filename', md.filename_contents)
                csum.set('target', 'content')

            # add all device checksums
            for csum in md.device_checksums:
                n_csum = ET.SubElement(rel, 'checksum')
                n_csum.text = csum.value
                n_csum.set('type', csum.kind.lower())
                n_csum.set('target', 'device')

            # add long description
            if md.release_description:
                markdown = md.release_description
                if md.issues:
                    markdown += '\n'
                    markdown += 'Security issues fixed:\n'
                    for issue in md.issues:
                        markdown += ' * {}\n'.format(issue.value)
                rel.append(_xml_from_markdown(markdown))

            # add details URL if set
            if md.details_url:
                child = ET.SubElement(rel, 'url')
                child.set('type', 'details')
                child.text = md.details_url

            # add source URL if set
            if md.source_url:
                child = ET.SubElement(rel, 'url')
                child.set('type', 'source')
                child.text = md.source_url

            # add sizes if set
            if md.release_installed_size:
                sz = ET.SubElement(rel, 'size')
                sz.set('type', 'installed')
                sz.text = str(md.release_installed_size)
            if md.release_download_size:
                sz = ET.SubElement(rel, 'size')
                sz.set('type', 'download')
                sz.text = str(md.release_download_size)

        # deliberately not including <category> here until 2020-01-01
        if False:                       # pylint: disable=using-constant-test
            cats = [] #lgtm [py/unreachable-statement]
            for md in mds:
                if not md.category:
                    continue
                if md.category.value not in cats:
                    cats.append(md.category.value)
                if md.category.fallbacks:
                    for fallback in md.category.fallbacks.split(','):
                        if fallback not in cats:
                            cats.append(fallback)
            if cats:
                categories = ET.SubElement(root, 'categories')
                for cat in cats:
                    ET.SubElement(categories, 'category').text = cat

        # provides shared by all releases
        elements = {}
        for md in mds:
            for guid in md.guids:
                if guid.value in elements:
                    continue
                child = ET.Element('firmware')
                child.set('type', 'flashed')
                child.text = guid.value
                elements[guid.value] = child
        if elements:
            parent = ET.SubElement(component, 'provides')
            for key in sorted(elements):
                parent.append(elements[key])

        # metadata shared by all releases
        elements = []
        for md in mds:
            if md.inhibit_download:
                child = ET.Element('value')
                child.set('key', 'LVFS::InhibitDownload')
                elements.append(('LVFS::InhibitDownload', None))
                break
        for md in mds:
            verfmt = md.verfmt_with_fallback
            if verfmt:
                if verfmt.fallbacks:
                    for fallback in verfmt.fallbacks.split(','):
                        elements.append(('LVFS::VersionFormat', fallback))
                elements.append(('LVFS::VersionFormat', verfmt.value))
                break
        if elements:
            parent = ET.SubElement(component, 'custom')
            for key, value in elements:
                child = ET.Element('value')
                child.set('key', key)
                child.text = value
                parent.append(child)

    # dump to file
    et = ET.ElementTree(root)
    et.write(filename,
             encoding='utf-8',
             xml_declaration=True,
             compression=5,
             pretty_print=True)

def _metadata_update_targets(remotes):
    """ updates metadata for a specific target """
    fws = db.session.query(Firmware).all()
    settings = _get_settings()

    # set destination path from app config
    download_dir = app.config['DOWNLOAD_DIR']
    if not os.path.exists(download_dir):
        os.mkdir(download_dir)

    # create metadata for each remote
    for r in remotes:
        fws_filtered = []
        for fw in fws:
            if fw.remote.name in ['private', 'deleted']:
                continue
            if not fw.signed_timestamp:
                continue
            if r.check_fw(fw):
                fws_filtered.append(fw)
        _generate_metadata_kind(os.path.join(download_dir, r.filename),
                                fws_filtered,
                                firmware_baseuri=settings['firmware_baseuri'])

        # all firmwares are contained in the correct metadata now
        for fw in fws_filtered:
            fw.is_dirty = False

def _metadata_update_pulp():

    """ updates metadata for Pulp """
    download_dir = app.config['DOWNLOAD_DIR']
    with open(os.path.join(download_dir, 'PULP_MANIFEST'), 'w') as manifest:

        # add metadata
        for basename in ['firmware.xml.gz', 'firmware.xml.gz.asc']:
            fn = os.path.join(download_dir, basename)
            if os.path.exists(fn):
                with open(fn, 'rb') as f:
                    checksum_signed_sha256 = hashlib.sha256(f.read()).hexdigest()
                manifest.write('%s,%s,%i\n' % (basename, checksum_signed_sha256, os.path.getsize(fn)))

        # add firmware in stable
        for fw in db.session.query(Firmware).join(Remote).filter(Remote.is_public):
            manifest.write('{},{},{}\n'.format(fw.filename,
                                               fw.checksum_signed_sha256,
                                               fw.mds[0].release_download_size))
