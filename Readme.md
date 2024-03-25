# A simple Spot Grid Martin Strategy

This script implements a spot grid trading strategy using OKX exchange WebSocket API. It manages spot grid trading positions, places buy and sell orders, and calculates profits based on market data received via WebSocket.

## Installation

### Clone the repository:

```bash
git clone https://github.com/your_username/spot-grid-martin.git
```

### Install dependencies:

```bash
pip install -r requirements.txt
```

### Usage

Run the script spot_grid_martin.py to start the spot grid trading bot. Ensure that you have configured the necessary API keys and other parameters in the script before running.

```bash
python spot_grid_martin.py
```

## Description

The script consists of the following components:

1.Configuration: Configure API keys, logging settings, and database path.

2.Database Models: Define SQLAlchemy ORM models for managing spot grid trading positions and statistics.

3.WebSocket Connection: Establish a WebSocket connection to the OKX exchange for receiving real-time market data.

4.Main Logic: Implement the main trading logic, including processing incoming market data, managing spot grid positions, placing buy and sell orders, and updating trading statistics.

5.Asynchronous Execution: Use asyncio to handle asynchronous WebSocket communication and retries for connection stability.

## License

This project is licensed under the MIT License - see the LICENSE file for details.