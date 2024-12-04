#!/usr/bin/env python3

"""
Web interface for Seestar INDI driver
Provides real-time monitoring and control with security
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, render_template, jsonify, request, Response, redirect, url_for
from flask_socketio import SocketIO, emit
from werkzeug.security import check_password_hash

from seestar_api import SeestarAPI
from seestar_config import config_manager
from seestar_logging import get_logger
from seestar_monitor import DeviceMonitor
from seestar_auth import auth_manager, require_auth, init_ssl

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = auth_manager.secret_key
socketio = SocketIO(app)

# Setup logging
logger = get_logger("SeestarWeb")

# Initialize API and monitor
api = SeestarAPI(
    host=config_manager.config.api.host,
    port=config_manager.config.api.port
)
monitor = DeviceMonitor(api)

# Register state change handler
@monitor.add_event_callback("state_change")
def handle_state_change(event):
    """Handle device state changes"""
    socketio.emit('state_update', event)

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if auth_manager.verify_password(username, password):
            token = auth_manager.generate_token(username)
            response = redirect(url_for('index'))
            response.set_cookie('token', token)
            return response
            
        return render_template('login.html', error="Invalid credentials")
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Handle logout"""
    response = redirect(url_for('login'))
    response.delete_cookie('token')
    return response

# Web routes
@app.route('/')
@require_auth
def index():
    """Main page"""
    return render_template(
        'index.html',
        state=monitor.get_state(),
        config=config_manager.config
    )

@app.route('/status')
@require_auth
def status():
    """Get current device status"""
    state = monitor.get_state()
    return jsonify({
        'connected': state.connected,
        'ra': state.ra,
        'dec': state.dec,
        'slewing': state.slewing,
        'tracking': state.tracking,
        'exposing': state.exposing,
        'filter_position': state.filter_position,
        'focus_position': state.focus_position,
        'temperature': state.focus_temperature,
        'error': state.error,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/config', methods=['GET', 'POST'])
@require_auth
def config():
    """Get or update configuration"""
    if request.method == 'POST':
        data = request.get_json()
        try:
            config_manager.update_config(
                data['section'],
                {data['key']: data['value']}
            )
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    else:
        return jsonify({
            'camera': config_manager.config.camera.__dict__,
            'focuser': config_manager.config.focuser.__dict__,
            'filterwheel': config_manager.config.filterwheel.__dict__,
            'api': config_manager.config.api.__dict__
        })

@app.route('/logs')
@require_auth
def logs():
    """Stream log file"""
    def generate():
        log_file = Path('logs/seestar.log')
        if not log_file.exists():
            return
        
        with open(log_file) as f:
            # First yield existing content
            content = f.read()
            yield content
            
            # Then tail for new content
            while True:
                content = f.read()
                if content:
                    yield content
                socketio.sleep(1)
                
    return Response(generate(), mimetype='text/plain')

# Control endpoints
@app.route('/control/goto', methods=['POST'])
@require_auth
def goto():
    """Slew to coordinates"""
    data = request.get_json()
    try:
        result = api.goto_target(
            str(data['ra']),
            str(data['dec']),
            data.get('target_name', 'Web Target')
        )
        return jsonify({'status': 'success' if result else 'error'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/control/stop', methods=['POST'])
@require_auth
def stop():
    """Stop movement"""
    try:
        result = api.stop_slew()
        return jsonify({'status': 'success' if result else 'error'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/control/expose', methods=['POST'])
@require_auth
def expose():
    """Start exposure"""
    data = request.get_json()
    try:
        result = monitor.start_exposure(
            float(data['duration']),
            int(data.get('gain', config_manager.config.camera.min_gain))
        )
        return jsonify({'status': 'success' if result else 'error'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/control/filter', methods=['POST'])
@require_auth
def filter_control():
    """Control filter wheel"""
    data = request.get_json()
    try:
        result = monitor.move_filter(int(data['position']))
        return jsonify({'status': 'success' if result else 'error'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/control/focus', methods=['POST'])
@require_auth
def focus_control():
    """Control focuser"""
    data = request.get_json()
    try:
        if 'position' in data:
            result = api.send_command(
                "method_sync",
                {
                    "method": "set_focus_position",
                    "params": {"position": int(data['position'])}
                }
            ) is not None
        elif 'relative' in data:
            current = monitor.state.focus_position
            result = api.send_command(
                "method_sync",
                {
                    "method": "set_focus_position",
                    "params": {"position": current + int(data['relative'])}
                }
            ) is not None
        elif data.get('auto', False):
            result = monitor.start_autofocus()
        else:
            return jsonify({'status': 'error', 'message': 'Invalid focus command'})
            
        return jsonify({'status': 'success' if result else 'error'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# WebSocket authentication
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    token = request.args.get('token')
    if not token or not auth_manager.verify_token(token):
        return False
    emit('state_update', monitor.get_state().__dict__)

def main():
    """Start web interface"""
    try:
        # Start device monitor
        monitor.start()
        
        # Initialize SSL
        cert_file, key_file = init_ssl()
        
        # Start web server
        host = config_manager.config.api.host
        port = 8080  # Web interface port
        
        logger.info(f"Starting secure web interface at https://{host}:{port}")
        socketio.run(
            app,
            host=host,
            port=port,
            certfile=cert_file,
            keyfile=key_file,
            debug=False
        )
        
    except KeyboardInterrupt:
        logger.info("Shutting down web interface")
        monitor.stop()
    except Exception as e:
        logger.error(f"Web interface error: {e}")
        monitor.stop()

if __name__ == '__main__':
    main()
