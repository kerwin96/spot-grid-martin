import traceback

import ccxt
from decimal import Decimal, ROUND_CEILING
import json
from datetime import datetime

with open(r'acc.json', 'r') as file:
    accounts = json.load(file)
    global okx, binance_test, binance
    okx = ccxt.okx({
        "apiKey": accounts['okx_apikey'],
        "secret": accounts['okx_secretkey'],
        "password": accounts['okx_passphrase'],
    })
    okx.httpsProxy = 'http://127.0.0.1:7890/'


def get_spot_order_okx_test(symbol, cl_order_id=None):
    try:
        okx.set_sandbox_mode(True)  # demo-trading
        contract = symbol.upper() + "/USDT"

        order = okx.fetch_order(id=None, symbol=contract, params={'clOrdId': cl_order_id})
        print(order)
        return order

    except Exception as e:
        traceback.print_exception(e)


def place_spot_order_okx_test(symbol, action, price, quota_amount=None, base_amount=None, cl_order_id=None):
    try:
        okx.set_sandbox_mode(True)  # demo-trading
        contract = symbol.upper() + "/USDT"

        # amount,price = get_spot_amount_from_usdt_okx(symbol, 12)

        # get_spot_amount_from_usdt_okx(symbol, 12)
        if base_amount:
            amount = base_amount
        elif quota_amount:
            amount = quota_amount / price
        else:
            return

        # 'tgtCcy': 'quote_ccy' 现货直接指定usdt
        if action == 'long':
            # stop_loss_price = price*0.97
            # print(stop_loss_price)
            # take_profit_price = price*1.1
            # print(take_profit_price)
            # order = okx.create_order(contract, 'limit', 'buy', 0.001,price=3200.0)
            order = okx.create_order(contract, 'limit', 'buy', amount, price=price,
                                     params={'tgtCcy': 'quote-ccy', 'clOrdId': cl_order_id})
            # tp_order = okx.create_order(contract, 'limit', 'sell', amount, price, {'takeProfitPrice': take_profit_price,  "posSide": "long"})
            # sl_order = okx.create_order(contract, 'limit', 'sell', amount, price, {'stopLossPrice': stop_loss_price,  "posSide": "long"})

            # print(order)
            return order
        elif action == 'short':
            order = okx.create_order(contract, 'limit', 'sell', amount, price=price,
                                     params={'tgtCcy': 'quote-ccy', 'clOrdId': cl_order_id})
            # print(order)
            return order

    except Exception as e:
        traceback.print_exception(e)


def cancel_spot_order_okx_test(symbol, cl_order_id=None):
    okx.set_sandbox_mode(True)  # demo-trading
    contract = symbol.upper() + "/USDT"
    order = okx.cancel_order(id=None, symbol=contract, params={'clOrdId': cl_order_id})
    return order


def place_order_okx_test(symbol, action):
    try:
        okx.set_sandbox_mode(True)  # demo-trading
        contract = symbol.upper() + "/USDT:USDT"
        leverage = okx.set_leverage(leverage=50, symbol=contract, params={'marginMode': 'isolated', 'posSide': action})

        # leverage = okx.set_margin_mode('isolated',contract,params={'leverage':50})
        amount, price = get_amount_from_usdt_okx(symbol, 500)

        # 'tgtCcy': 'quote_ccy' 现货直接指定usdt
        if action == 'long':
            stop_loss_price = price * 0.97
            print(stop_loss_price)
            take_profit_price = price * 1.1
            print(take_profit_price)
            order = okx.create_order(contract, 'market', 'buy', amount,
                                     params={"posSide": "long", 'marginMode': 'isolated'})
            tp_order = okx.create_order(contract, 'limit', 'sell', amount, price,
                                        {'takeProfitPrice': take_profit_price, "posSide": "long"})
            sl_order = okx.create_order(contract, 'limit', 'sell', amount, price,
                                        {'stopLossPrice': stop_loss_price, "posSide": "long"})



        elif action == 'short':
            stop_loss_price = price * 1.03
            take_profit_price = price * 0.9
            order = okx.create_order(contract, 'market', 'sell', amount,
                                     params={"posSide": "short", 'marginMode': 'isolated'})
            tp_order = okx.create_order(contract, 'limit', 'buy', amount, price,
                                        {'takeProfitPrice': take_profit_price, "posSide": "short"})
            sl_order = okx.create_order(contract, 'limit', 'buy', amount, price,
                                        {'stopLossPrice': stop_loss_price, "posSide": "short"})
    except Exception as e:
        traceback.print_exception(e)


def close_order_okx_test(symbol, action):
    okx.set_sandbox_mode(True)  # demo-trading
    contract = symbol.upper() + "/USDT:USDT"
    sz = get_amount_from_usdt_okx(symbol, 500)
    if action == 'long':
        order = okx.create_order(contract, 'market', 'sell', 1,
                                 params={'mgnMode': 'isolated', "posSide": "long", 'sz': sz})
    elif action == 'short':
        order = okx.create_order(contract, 'market', 'buy', 1,
                                 params={'mgnMode': 'isolated', "posSide": "short", 'sz': sz})
    return order


def get_spot_position_amount(symbol):
    okx.set_sandbox_mode(True)
    contract = symbol.upper()
    return okx.fetch_balance()

def get_spot_amount_from_usdt_okx(symbol, usdt_amount):
    okx.set_sandbox_mode(True)
    contract = symbol.upper() + "/USDT"
    price = (okx.fetch_ticker(contract))['close']
    print(price)
    coin_amount = usdt_amount / price
    # print(coin_amount)
    # return coin_amount
    market = okx.market(contract)
    contract_size = market['contractSize']

    print(market)

    # amount = round_decimal_up(usdt_amount / price, precision)
    # print(amount)
    # notional = market['info']['filters'][5]['notional']
    # notional_amount = round_decimal_up(float(notional) / price, precision)
    # amount = max(notional_amount, amount)
    amount = int(usdt_amount / (contract_size * price))
    return amount, price


def get_market_info(symbol):
    okx.set_sandbox_mode(True)
    contract = symbol.upper().replace("-","/")
    print(contract)
    markets = okx.load_markets()
    # price = (okx.fetch_ticker(contract))['close']
    # coin_amount = usdt_amount / price
    # print(coin_amount)
    # return coin_amount

    market = okx.market(contract)
    # contract_size = market['contractSize']

    # print("market",market)

    # amount = round_decimal_up(usdt_amount / price, precision)
    # print(amount)
    # notional = market['info']['filters'][5]['notional']
    # notional_amount = round_decimal_up(float(notional) / price, precision)
    # amount = max(notional_amount, amount)
    # amount = int(usdt_amount / (contract_size * price))
    return market


def get_amount_from_usdt_okx(symbol, usdt_amount):
    okx.set_sandbox_mode(True)
    contract = symbol.upper() + "/USDT:USDT"
    print(contract)
    price = (okx.fetch_ticker(contract))['close']
    coin_amount = usdt_amount / price
    # print(coin_amount)
    # return coin_amount
    market = okx.market(contract)
    contract_size = market['contractSize']

    # print(market)

    # amount = round_decimal_up(usdt_amount / price, precision)
    # print(amount)
    # notional = market['info']['filters'][5]['notional']
    # notional_amount = round_decimal_up(float(notional) / price, precision)
    # amount = max(notional_amount, amount)
    amount = int(usdt_amount / (contract_size * price))
    return amount, price


def get_unrealized_profit_okx(symbol):
    try:
        contract = symbol.upper() + "/USDT:USDT"
        okx.set_sandbox_mode(True)
        postion = okx.fetch_position(symbol=contract)
        # postion=okx.fetch_positions()
        unrealizedPnl = round(postion['unrealizedPnl'], 2)
        return unrealizedPnl
    except Exception as e:
        traceback.print_exception(e)


def get_today_realized_profit_okx(symbol):
    try:
        contract = symbol.upper() + "/USDT:USDT"
        okx.set_sandbox_mode(True)

        # 获取当前日期
        today = datetime.today()

        # 将时间设置为0点
        midnight = datetime(today.year, today.month, today.day)

        # 计算时间戳并转换为毫秒
        timestamp_milliseconds = int(midnight.timestamp() * 1000)

        orders = okx.fetch_closed_orders(symbol=contract, since=timestamp_milliseconds)
        total_pnl = 0.0;
        total_fee = 0.0;
        for order in orders:
            pnl = order['info']['pnl']
            fee = order['info']['fee']
            total_fee += float(fee)
            total_pnl += float(pnl)
        profit = round(total_pnl + total_fee, 2)
        return profit
    except Exception as e:
        traceback.print_exception(e)


# print(get_today_realized_profit_okx('btc'))
# print(get_unrealized_profit_okx('btc'))
# print(get_amount_from_usdt_okx('btc', 500))
# place_order_okx_test('inj','short')
# close_order_okx_test('btc','short')


# place_order_binance_test('BTCUSDT','long')
# print(place_spot_order_okx_test('BTC', 'buy', 71000,quota_amount=0.0001689))

# print(place_spot_order_okx_test('BTC', 'short', 71000,quota_amount=0.0001689))
get_spot_order_okx_test('ARB', 'ARB1712409844767')
# print(get_market_info('eth'))
# print(get_spot_position_amount('BCH'))