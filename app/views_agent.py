#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Richard Hughes <richard@hughsie.com>
# Licensed under the GNU General Public License Version 2

import json
import datetime

from flask import request, url_for, redirect, flash, Response, render_template, g
from flask_login import login_required

from app import app, db

from .models import Agent, AgentApproval
from .util import _error_internal, _error_permission_denied, _event_log
from .util import _json_success, _json_error, _get_client_address

@app.route('/lvfs/agent/all')
@login_required
def agent_list():
    agents = db.session.query(Agent).\
                    order_by(Agent.agent_id.desc()).all()
    return render_template('agent-list.html', agents=agents)

@app.route('/lvfs/agent/<agent_id>/json')
@login_required
def agent_json(agent_id):
    agent = db.session.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        return _error_permission_denied('Agent does not exist')
    return Response(response=agent.json,
                    status=400,
                    mimetype="application/json")

@app.route('/lvfs/agent/<agent_id>/details')
@login_required
def agent_details(agent_id):
    agent = db.session.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        return _error_permission_denied('Agent does not exist')
    return render_template('agent-details.html', agent=agent)

@app.route('/lvfs/agent/<agent_id>/delete')
@login_required
def agent_delete(agent_id):
    agent = db.session.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        return _error_internal('No agent found!')
    db.session.delete(agent)
    db.session.commit()
    flash('Deleted agent', 'info')
    return redirect(url_for('.agent_list'))

@app.route('/lvfs/agent/<agent_id>/approval/<checksum>/add')
@login_required
def agent_approval_add(agent_id, checksum):

    # check does not already exist
    approval = db.session.query(AgentApproval).\
                    filter(AgentApproval.checksum == checksum).\
                    filter(AgentApproval.agent_id == agent_id).\
                    first()
    if approval:
        flash("AgentApproval %s already exists for this agent" % checksum, 'warning')
        return redirect(url_for('.agent_details', agent_id=agent_id))
    approval = AgentApproval(checksum, agent_id=agent_id, user_id=g.user.user_id)
    db.session.add(approval)
    db.session.commit()

    # success
    _event_log('Added approval for %s for agent %s' % (checksum, agent_id))
    return redirect(url_for('.agent_details', agent_id=agent_id))

@app.route('/lvfs/agent/<agent_id>/action/<fwupd_id>/<checksum>/add')
@login_required
def agent_action_add(agent_id, fwupd_id, checksum):

    # success
    _event_log('Added action for %s:%s for agent %s' % (checksum, fwupd_id, agent_id))
    return redirect(url_for('.agent_details', agent_id=agent_id))

# no login required
@app.route('/lvfs/agent/register', methods=['POST'])
def agent_register():

    # parse JSON data
    json_request = request.data.decode('utf8')
    try:
        item = json.loads(json_request)
    except ValueError as e:
        return _json_error('No JSON object could be decoded: ' + str(e))

    # check we got enough data
    for key in ['ReportVersion', 'AgentId']:
        if not key in item:
            return _json_error('invalid data, expected %s' % key)
        if item[key] is None:
            return _json_error('missing data, expected %s' % key)

    # parse only this version
    if item['ReportVersion'] != 1:
        return _json_error('version not supported')

    # add each firmware agent
    agent_hash = item['AgentId']

    # update any old agent
    agent = db.session.query(Agent).filter(Agent.agent_hash == agent_hash).first()
    if agent:
        return _json_error('agent is already registered')

    # save a new agent in the database
    agent = Agent(agent_hash=agent_hash, addr=_get_client_address())
    db.session.add(agent)
    db.session.commit()

    # success
    _event_log('Registered agent %s' % agent_hash)
    return _json_success('agent registered')

# no login required
@app.route('/lvfs/agent/unregister', methods=['POST'])
def agent_unregister():

    # parse JSON data
    json_request = request.data.decode('utf8')
    try:
        item = json.loads(json_request)
    except ValueError as e:
        return _json_error('No JSON object could be decoded: ' + str(e))

    # check we got enough data
    for key in ['ReportVersion', 'AgentId']:
        if not key in item:
            return _json_error('invalid data, expected %s' % key)
        if item[key] is None:
            return _json_error('missing data, expected %s' % key)

    # parse only this version
    if item['ReportVersion'] != 1:
        return _json_error('version not supported')

    # add each firmware agent
    agent_hash = item['AgentId']

    # find agent
    agent = db.session.query(Agent).filter(Agent.agent_hash == agent_hash).first()
    if not agent:
        return _json_error('agent is not registered')

    # delete agent from the database
    db.session.delete(agent)
    db.session.commit()

    # success
    _event_log('Unregistered agent %s' % agent_hash)
    return _json_success('agent unregistered')

# no login required
@app.route('/lvfs/agent/sync', methods=['POST'])
def agent_sync():

    # parse JSON data
    json_request = request.data.decode('utf8')
    try:
        item = json.loads(json_request)
    except ValueError as e:
        return _json_error('No JSON object could be decoded: ' + str(e))

    # check we got enough data
    for key in ['ReportVersion', 'AgentId']:
        if not key in item:
            return _json_error('invalid data, expected %s' % key)
        if item[key] is None:
            return _json_error('missing data, expected %s' % key)

    # parse only this version
    if item['ReportVersion'] != 1:
        return _json_error('version not supported')

    # add each firmware agent
    agent_hash = item['AgentId']

    # find agent
    agent = db.session.query(Agent).filter(Agent.agent_hash == agent_hash).first()
    if not agent:
        return _json_error('agent is not already registered')

    # update database
    agent.json = json_request
    agent.timestamp = datetime.datetime.utcnow()
    db.session.commit()

    # get current approved checksums
    checksums = []
    for approval in db.session.query(AgentApproval).\
                        order_by(AgentApproval.timestamp.desc()).all():
        checksums.append(approval.checksum)

    # get any agent actions
    actions = []
    if 0:
        action = {}
        action['Task'] = 'upgrade'
        action['AgentDeviceId'] = '4588a84d1cfa1ddb273e9df28f6a44927e9b4e99'
        action['Checksum'] = '0e7e9dafeb4dcc144d1434759ebf7bd71ea2a4d7'
        actions.append(action)

    # return blob
    item = {}
    item['success'] = True
    if checksums:
        item['approved'] = checksums
    if actions:
        item['actions'] = actions
    item['msg'] = 'agent updated'
    dat = json.dumps(item, sort_keys=True, indent=4, separators=(',', ': '))
    return Response(response=dat,
                    status=200,
                    mimetype="application/json")
