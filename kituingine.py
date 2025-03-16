from serial import Serial, SerialException
import time
from datetime import datetime
import sys
import json
import asyncio
import websockets
from aiohttp import web
import os

class BinMonitor:
    def __init__(self, port='COM21', baud_rate=9600):
        self.port = port
        self.baud_rate = baud_rate
        self.ser = None
        self.connected_clients = set()

    async def connect_serial(self):
        """Establish serial connection with NodeMCU"""
        try:
            self.ser = Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=1,
                bytesize=8,
                parity='N',
                stopbits=1
            )
            print(f"[{self.get_timestamp()}] Serial connection established on {self.port}")
            return True
        except Exception as e:
            print(f"[{self.get_timestamp()}] Serial connection error: {e}")
            return False

    def get_timestamp(self):
        """Get current timestamp"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def parse_distance(self, distance_str):
        """Parse distance value from string, removing units"""
        distance_str = distance_str.replace('Distance:', '').strip()
        return float(distance_str.replace(' cm', ''))

    async def websocket_handler(self, websocket):
        """Handle WebSocket connections"""
        try:
            self.connected_clients.add(websocket)
            print(f"[{self.get_timestamp()}] WebSocket client connected")
            while True:
                if self.ser and self.ser.in_waiting:
                    data = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    print(f"[{self.get_timestamp()}] Received data from serial: {data}")
                    if data:
                        try:
                            parts = data.split(',')
                            if len(parts) == 2:
                                distance = self.parse_distance(parts[0])
                                bin_status = parts[1].replace('Bin Status:', '').strip()
                                
                                message = json.dumps({
                                    'distance': distance,
                                    'bin_status': bin_status,
                                    'timestamp': self.get_timestamp()
                                })
                                
                                await websocket.send(message)
                                print(f"[{self.get_timestamp()}] Sent message to WebSocket client: {message}")
                        except Exception as e:
                            print(f"Error processing data: {e}")
                await asyncio.sleep(0.1)
        except websockets.exceptions.ConnectionClosed:
            print(f"[{self.get_timestamp()}] WebSocket client disconnected")
        finally:
            self.connected_clients.remove(websocket)

    async def handle_index(self, request):
        """Serve the HTML dashboard"""
        template_path = os.path.join('templates', 'index.html')
        with open(template_path, 'r') as f:
            return web.Response(text=f.read(), content_type='text/html')

    async def start_server(self):
        """Start the web and WebSocket servers"""
        if not await self.connect_serial():
            return

        app = web.Application()
        app.router.add_get('/', self.handle_index)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 8080)
        
        await site.start()
        print(f"[{self.get_timestamp()}] Web server started at http://localhost:8080")
        
        # Use the websocket_handler directly without path parameter
        ws_server = await websockets.serve(self.websocket_handler, 'localhost', 8765)
        print(f"[{self.get_timestamp()}] WebSocket server started at ws://localhost:8765")
        
        await asyncio.Future()  # run forever

    def cleanup(self):
        """Clean up resources"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"[{self.get_timestamp()}] Serial connection closed")

async def main():
    monitor = BinMonitor()
    try:
        await monitor.start_server()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        monitor.cleanup()

if __name__ == "__main__":
    asyncio.run(main())