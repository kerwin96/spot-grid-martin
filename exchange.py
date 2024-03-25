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

    binance_test = ccxt.binance({
        "apiKey": accounts['binance_test_api_key'],
        "secret": accounts['binance_test_secret_key'],
    })
    binance_test.options = {'defaultType': 'future', 'adjustForTimeDifference': True, 'defaultTimeInForce': 'GTC'}
    binance_test.set_sandbox_mode(True)
    binance = ccxt.binance({
        "apiKey": accounts['binance_api_key'],
        "secret": accounts['binance_secret_key'],
    })
    binance_test.options = {'defaultType': 'future', 'adjustForTimeDifference': True, 'defaultTimeInForce': 'GTC'}


def get_spot_order_okx_test(symbol, cl_order_id=None):
    try:
        okx.set_sandbox_mode(True)  # demo-trading
        contract = symbol.upper() + "/USDT"

        order = okx.fetch_order(id=None,symbol=contract,params={'clOrdId':cl_order_id})
        # print(order)
        return order

    except Exception as e:
        traceback.print_exception(e)


def place_spot_order_okx_test(symbol, action, price, quota_amount=None, base_amount=None,cl_order_id=None):
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
            order = okx.create_order(contract, 'limit', 'buy', amount, price=price, params={'tgtCcy': 'quote-ccy','clOrdId':cl_order_id})
            # tp_order = okx.create_order(contract, 'limit', 'sell', amount, price, {'takeProfitPrice': take_profit_price,  "posSide": "long"})
            # sl_order = okx.create_order(contract, 'limit', 'sell', amount, price, {'stopLossPrice': stop_loss_price,  "posSide": "long"})

            # print(order)

        elif action == 'short':
            order = okx.create_order(contract, 'limit', 'sell', amount, price=price,
                                     params={'tgtCcy': 'quote-ccy','clOrdId':cl_order_id})
            # print(order)
        return order

    except Exception as e:
        traceback.print_exception(e)


def cancel_spot_order_okx_test(symbol, cl_order_id=None):
    okx.set_sandbox_mode(True)  # demo-trading
    contract = symbol.upper() + "/USDT"
    order = okx.cancel_order(id=None,symbol=contract, params={'clOrdId':cl_order_id})
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


def close_order_binance_test(symbol, action):
    binance_test.set_sandbox_mode(True)  # demo-trading
    contract = symbol.upper() + "/USDT:USDT"
    if action == 'long':
        order = binance_test.create_order(contract, 'market', 'sell', 1,
                                          params={'mgnMode': 'isolated', "posSide": "long", 'sz': 1})
    elif action == 'short':
        order = binance_test.create_order(contract, 'market', 'buy', 1,
                                          params={'mgnMode': 'isolated', "posSide": "short", 'sz': 1})
    return order


# order = place_order('eth','long')
# #{'info': {'clOrdId': 'e847386590ce4dBCfc5c5b9471ac78b5', 'ordId': '660417488194207801', 'sCode': '0', 'sMsg': 'Order placed', 'tag': 'e847386590ce4dBC'}, 'id': '660417488194207801', 'clientOrderId': 'e847386590ce4dBCfc5c5b9471ac78b5', 'timestamp': None, 'datetime': None, 'lastTradeTimestamp': None, 'lastUpdateTimestamp': None, 'symbol': 'ETH/USDT:USDT', 'type': 'market', 'timeInForce': None, 'postOnly': None, 'side': 'sell', 'price': None, 'stopLossPrice': None, 'takeProfitPrice': None, 'stopPrice': None, 'triggerPrice': None, 'average': None, 'cost': None, 'amount': None, 'filled': None, 'remaining': None, 'status': None, 'fee': None, 'trades': [], 'reduceOnly': False, 'fees': []}

# print(order)
# close_order('btc','short')

def round_decimal_up(number, n):
    # 将输入的数字转换为Decimal对象
    decimal_number = Decimal(str(number))

    # 构建一个Decimal对象，用于指定小数位数和舍入方式
    rounding_factor = Decimal("1") / Decimal("10") ** n

    # 使用ROUND_CEILING舍入方式进行舍入
    rounded_number = (decimal_number / rounding_factor).quantize(Decimal("1"), rounding=ROUND_CEILING) * rounding_factor

    return rounded_number


def get_amount_from_usdt_bianance(symbol, usdt_amount):
    price = (binance.fetch_ticker(symbol))['close']
    market = exchange.market(symbol)
    # print(market)
    precision = market['precision']['amount']
    amount = round_decimal_up(quote_amount / price, precision)
    notional = market['info']['filters'][5]['notional']

    # amount = float(f'%.{precision}g' % ())
    # print(amount)
    # print(float(notional) / price)
    notional_amount = round_decimal_up(float(notional) / price, precision)
    amount = max(notional_amount, amount)
    return amount


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


def get_amount_from_usdt_okx(symbol, usdt_amount):
    okx.set_sandbox_mode(True)
    contract = symbol.upper() + "/USDT:USDT"
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
def place_order_binance_test(symbol, action):
    # binance_test.set_sandbox_mode(True)  # demo-trading
    if action in ['buy', 'long']:
        side = 'buy'
    elif action in ['sell', 'short']:
        side = 'sell'

    amount = get_amount_from_usdt_bianance(symbol, 500)

    order = client.new_order(symbol=symbol, side=action, type=type, quantity=amount, close_postion=True)
    # print(order)
    return order


# place_order_binance_test('BTCUSDT','long')

# print(place_spot_order_okx_test('ATOM', 'long', 11.11, base_amount=1))
# get_spot_order_okx_test('sui','SUI1711020521203')