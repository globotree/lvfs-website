#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017-2018 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: GPL-2.0+

import datetime

from sqlalchemy import and_

from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required

from lvfs import db

from lvfs.models import Analytic, Client, Report, Useragent, UseragentKind, SearchEvent, AnalyticVendor
from lvfs.models import _get_datestr_from_datetime, _split_search_string
from lvfs.util import admin_login_required
from lvfs.util import _get_chart_labels_months, _get_chart_labels_days

bp_analytics = Blueprint('analytics', __name__, template_folder='templates')

@bp_analytics.route('/')
@bp_analytics.route('/month')
@login_required
@admin_login_required
def route_month():
    """ A analytics screen to show information about users """

    # this is somewhat klunky
    data = []
    now = datetime.date.today() - datetime.timedelta(days=1)
    for _ in range(30):
        datestr = _get_datestr_from_datetime(now)
        analytic = db.session.query(Analytic).\
                        filter(Analytic.datestr == datestr).\
                        first()
        if analytic:
            data.append(int(analytic.cnt))
        else:
            data.append(0)

        # back one day
        now -= datetime.timedelta(days=1)

    return render_template('analytics-month.html',
                           category='analytics',
                           labels_days=_get_chart_labels_days()[::-1],
                           data_days=data[::-1])

@bp_analytics.route('/year')
@bp_analytics.route('/year/<int:ts>')
@login_required
@admin_login_required
def route_year(ts=3):
    """ A analytics screen to show information about users """

    # this is somewhat klunky
    data = []
    now = datetime.date.today() - datetime.timedelta(days=1)
    for _ in range(12 * ts):
        datestrold = _get_datestr_from_datetime(now)
        now -= datetime.timedelta(days=30)
        datestrnew = _get_datestr_from_datetime(now)
        analytics = db.session.query(Analytic).\
                        filter(Analytic.datestr < datestrold).\
                        filter(Analytic.datestr > datestrnew).\
                        all()

        # sum up all the totals for each day in that month
        cnt = 0
        for analytic in analytics:
            cnt += analytic.cnt
        data.append(int(cnt))

    return render_template('analytics-year.html',
                           category='analytics',
                           labels_months=_get_chart_labels_months(ts)[::-1],
                           data_months=data[::-1])

def _user_agent_wildcard(user_agent):
    tokens = user_agent.split('/')
    if len(tokens) != 2:
        return user_agent
    if tokens[0] == 'Mozilla':
        return 'browser'
    if tokens[0] == 'Java':
        return 'bot'
    versplt = tokens[1].split('.')
    if len(versplt) != 3:
        return user_agent
    return tokens[0] + ' ' + '.'.join((versplt[0], versplt[1], 'x'))

@bp_analytics.route('/user_agent')
@bp_analytics.route('/user_agent/<kind>')
@bp_analytics.route('/user_agent/<kind>/<int:timespan_days>')
@login_required
@admin_login_required
def route_user_agents(kind='APP', timespan_days=30):
    """ A analytics screen to show information about users """

    # map back to UseragentKind
    try:
        kind_enum = UseragentKind[kind]
    except KeyError as e:
        flash('Unable to view analytic type: {}'.format(str(e)), 'danger')
        return redirect(url_for('analytics.route_user_agents'))

    # get data for this time period
    cnt_total = {}
    cached_cnt = {}
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    datestr_start = _get_datestr_from_datetime(yesterday - datetime.timedelta(days=timespan_days))
    datestr_end = _get_datestr_from_datetime(yesterday)
    for ug in db.session.query(Useragent).\
                    filter(Useragent.kind == kind_enum.value).\
                    filter(and_(Useragent.datestr > datestr_start,
                                Useragent.datestr <= datestr_end)):
        user_agent_safe = _user_agent_wildcard(ug.value)
        if kind == 'FWUPD':
            splt = user_agent_safe.split('.', 3)
            if len(splt) == 3:
                user_agent_safe = '{}.{}.x'.format(splt[0], splt[1])
        key = str(ug.datestr) + user_agent_safe
        if key not in cached_cnt:
            cached_cnt[key] = ug.cnt
        else:
            cached_cnt[key] += ug.cnt
        if not user_agent_safe in cnt_total:
            cnt_total[user_agent_safe] = ug.cnt
            continue
        cnt_total[user_agent_safe] += ug.cnt

    # find most popular user agent strings
    most_popular = []
    for key, value in sorted(iter(cnt_total.items()), key=lambda k_v: (k_v[1], k_v[0]), reverse=True):
        most_popular.append(key)
        if len(most_popular) >= 6:
            break

    # generate enough for the template
    datasets = []
    palette = [
        'ef4760',   # red
        'ffd160',   # yellow
        '06c990',   # green
        '2f8ba0',   # teal
        '845f80',   # purple
        'ee8510',   # orange
    ]
    idx = 0
    for value in most_popular:
        dataset = {}
        dataset['label'] = value
        dataset['color'] = palette[idx % 6]
        idx += 1
        data = []
        for i in range(timespan_days):
            datestr = _get_datestr_from_datetime(yesterday - datetime.timedelta(days=i))
            key = str(datestr) + value
            dataval = 'NaN'
            if key in cached_cnt:
                dataval = str(cached_cnt[key])
            data.append(dataval)
        dataset['data'] = '[' + ', '.join(data[::-1]) + ']'
        datasets.append(dataset)
    return render_template('analytics-user-agent.html',
                           category='analytics',
                           kind=kind,
                           labels_user_agent=_get_chart_labels_days(timespan_days)[::-1],
                           datasets=datasets)

@bp_analytics.route('/vendor')
@bp_analytics.route('/vendor/<int:timespan_days>')
@login_required
@admin_login_required
def route_vendor(timespan_days=30):
    """ A analytics screen to show information about users """

    # get data for this time period
    cnt_total = {}
    cached_cnt = {}
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    datestr_start = _get_datestr_from_datetime(yesterday - datetime.timedelta(days=timespan_days))
    datestr_end = _get_datestr_from_datetime(yesterday)
    for ug in db.session.query(AnalyticVendor).\
                    filter(and_(AnalyticVendor.datestr > datestr_start,
                                AnalyticVendor.datestr <= datestr_end)):
        display_name = ug.vendor.display_name
        key = str(ug.datestr) + display_name
        if key not in cached_cnt:
            cached_cnt[key] = ug.cnt
        if not display_name in cnt_total:
            cnt_total[display_name] = ug.cnt
            continue
        cnt_total[display_name] += ug.cnt

    # find most popular user agent strings
    most_popular = []
    for key, value in sorted(iter(cnt_total.items()), key=lambda k_v: (k_v[1], k_v[0]), reverse=True):
        most_popular.append(key)
        if len(most_popular) >= 6:
            break

    # generate enough for the template
    datasets = []
    palette = [
        'ef4760',   # red
        'ffd160',   # yellow
        '06c990',   # green
        '2f8ba0',   # teal
        '845f80',   # purple
        'ee8510',   # orange
    ]
    idx = 0
    for value in most_popular:
        dataset = {}
        dataset['label'] = value
        dataset['color'] = palette[idx % 6]
        idx += 1
        data = []
        for i in range(timespan_days):
            datestr = _get_datestr_from_datetime(yesterday - datetime.timedelta(days=i))
            key = str(datestr) + value
            dataval = 'NaN'
            if key in cached_cnt:
                dataval = str(cached_cnt[key])
            data.append(dataval)
        dataset['data'] = '[' + ', '.join(data[::-1]) + ']'
        datasets.append(dataset)
    return render_template('analytics-vendor.html',
                           category='analytics',
                           labels_user_agent=_get_chart_labels_days(timespan_days)[::-1],
                           datasets=datasets)

@bp_analytics.route('/clients')
@login_required
@admin_login_required
def route_clients():
    """ A analytics screen to show information about users """

    clients = db.session.query(Client).\
                    order_by(Client.timestamp.desc()).\
                    limit(25).all()
    return render_template('analytics-clients.html',
                           category='analytics',
                           clients=clients)

@bp_analytics.route('/reports')
@login_required
@admin_login_required
def route_reports():
    """ A analytics screen to show information about users """
    reports = db.session.query(Report).\
                    order_by(Report.timestamp.desc()).\
                    limit(25).all()
    return render_template('analytics-reports.html',
                           category='analytics',
                           reports=reports)

@bp_analytics.route('/search_history')
@login_required
@admin_login_required
def route_search_history():
    search_events = db.session.query(SearchEvent).\
                        order_by(SearchEvent.timestamp.desc()).\
                        limit(1000).all()
    return render_template('analytics-search-history.html',
                           category='analytics',
                           search_events=search_events)

@bp_analytics.route('/search_stats')
@bp_analytics.route('/search_stats/<int:limit>')
@login_required
@admin_login_required
def route_search_stats(limit=20):
    search_events = db.session.query(SearchEvent).\
                        order_by(SearchEvent.timestamp.desc()).\
                        limit(99999).all()

    keywords = {}
    for ev in search_events:
        for tok in _split_search_string(ev.value):
            if tok in keywords:
                keywords[tok] += 1
                continue
            keywords[tok] = 1
    results = []
    for keyword in keywords:
        results.append((keyword, keywords[keyword]))
    results.sort(key=lambda k: k[1], reverse=True)

    # generate the graph data
    labels = []
    data = []
    for res in results[0:limit]:
        labels.append(str(res[0]))
        data.append(res[1])
    return render_template('analytics-search-stats.html',
                           category='analytics',
                           labels=labels, data=data)
