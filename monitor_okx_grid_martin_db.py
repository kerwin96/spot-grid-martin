# !/usr/bin/env python
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Boolean, text, func
from sqlalchemy.orm import sessionmaker
import sqlalchemy
from ccxt.base.errors import OrderNotFound
import json
from datetime import datetime
from exchange import place_spot_order_okx_test, get_spot_order_okx_test, cancel_spot_order_okx_test,get_market_info
from websockets.exceptions import ConnectionClosedError
import websockets
import logging
import asyncio
from logging.handlers import TimedRotatingFileHandler
from decimal import Decimal, ROUND_DOWN
#todo 订单部分成交1h其余还未成交
#todo btc订单buy amount数量不对

# 设置 SQLAlchemy 的日志级别为 ERROR

logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)

# 创建日志记录器并设置级别为 INFO
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 创建文件处理程序并设置级别为 INFO
file_handler = TimedRotatingFileHandler('spot-grid-martin.log', when='midnight', interval=1, backupCount=1,
                                        encoding='utf-8')
console_handler = logging.StreamHandler()
# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
# 将文件处理程序添加到日志记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)
# config_logging(logging, logging.DEBUG)
Base = sqlalchemy.orm.declarative_base()
path = 'crypto.db'
# 创建数据库引擎和会话
engine = create_engine(f'sqlite:///{path}', echo=False, pool_size=10)
quota_amount = 12
executor = None


class SpotGrid(Base):
    __tablename__ = 'spot_grid'
    id = Column(Integer(), primary_key=True, autoincrement=True)
    symbol = Column(String(20))
    num = Column(Integer())
    buy_price = Column(Float(10))
    down_price = Column(Float(10))
    down_buy_price = Column(Float(10))
    up_price = Column(Float(10))
    sell_price = Column(Float(10))
    buy_amount = Column(Float(10))  # 买入数量
    position_amount = Column(Float(10))  # 实际持仓数量（扣除买入手续费）
    sell_amount = Column(Float(10)) # 卖出数量
    buy_state = Column(Integer())  # null为买入未成交 1成交
    sell_state = Column(Integer())  # null 未卖出 0为卖出未成交 1成交
    buy_fee = Column(Float(10))
    sell_fee = Column(Float(10))
    buy_order_id = Column(String(20))
    sell_order_id = Column(String(20))
    realized_profit = Column(Float(10))  # 该仓位已实现所获利润
    buy_time = Column(DateTime)
    sell_time = Column(DateTime)


class Spot(Base):
    __tablename__ = 'spot'
    id = Column(Integer(), primary_key=True, autoincrement=True)
    symbol = Column(String(20))
    all_position_amount = Column(Float(10))  # 开仓时加 平仓时减
    avg_buy_price = Column(Float(10))  # 开仓平仓时重新计算 所有未平仓价格*数量/所有数量
    all_value = Column(Float(10))  #
    all_realized_profit = Column(Float(10))  # 所有仓位已实现所获利润   平仓时计算
    all_unrealized_profit = Column(Float(10))  # 所有仓位未实现利润  每次计算
    all_buy_fee = Column(Float(10))
    all_sell_fee = Column(Float(10))


Base.metadata.create_all(engine)


def get_session():
    session = sessionmaker(bind=engine)
    return session()


# def align_precision(a, symbol):
#     a_with_precision = Decimal(a).quantize(Decimal(str(precision_map.get(symbol))), rounding=ROUND_DOWN)
#     return a_with_precision

def process_kline(data):
    event_time = datetime.fromtimestamp(int(data['data'][0]['ts']) / 1000.0)
    symbol = data['arg']["instId"]
    mark_price = float(data['data'][0]['last'])
    logger.info(f'{symbol} mark price:{mark_price}')
    with get_session() as session:

        record = session.query(SpotGrid).filter_by(symbol=symbol, sell_price=None).order_by(
            SpotGrid.buy_time.desc()).first()
        if not record:
            # 初始化
            logger.info(f'----{symbol}无订单，准备创建第一个订单-----')
            spot_grid = SpotGrid()
            spot_grid.symbol = symbol
            spot_grid.num = 0
            spot_grid.buy_time = event_time
            spot_grid.buy_order_id = symbol[:-5] + data['data'][0]['ts']
            spot_grid.realized_profit = 0
            spot_grid.buy_fee = 0
            spot_grid.sell_fee = 0
            order = place_spot_order_okx_test(symbol[:-5], 'long', mark_price, base_amount=quota_amount / mark_price,
                                              cl_order_id=spot_grid.buy_order_id)
            logger.info(order)
            if not order or order['info']['sCode'] != '0':
                return
            session.add(spot_grid)
            session.commit()
        spot_record = session.query(Spot).filter_by(symbol=symbol).first()
        if not spot_record:
            spot = Spot()
            spot.symbol = symbol
            spot.all_position_amount = 0
            spot.avg_buy_price = 0
            spot.all_value = 0
            spot.all_realized_profit = 0
            spot.all_unrealized_profit = 0
            spot.all_sell_fee = 0
            spot.all_buy_fee = 0
            session.add(spot)
            session.commit()


        elif record:
            if record.sell_state == 0:  # 卖出未成交
                order = get_spot_order_okx_test(symbol[:-5], record.sell_order_id)
                state = order['info']['state']
                if state == 'filled':
                    logger.info(f'卖出订单已成交-symbol:{record.symbol}-order_id:{record.sell_order_id}', )
                    record.sell_amount= float(order['info']['accFillSz'])
                    record.sell_price = float(order['info']['avgPx'])
                    record.sell_fee = float(order['info']['fee'])
                    record.realized_profit = (record.sell_price - record.buy_price) * record.sell_amount + record.sell_fee
                    record.sell_state = 1
                    session.commit()
                    spot_record = session.query(Spot).filter_by(symbol=symbol).first()
                    # 计算统计表
                    spot_grid_records = session.query(SpotGrid).filter_by(symbol=symbol).all()
                    all_value = 0
                    all_position_amount = 0
                    all_realized_profit = 0
                    all_buy_fee = 0
                    all_sell_fee = 0
                    for spot_grid_record in spot_grid_records:
                        if spot_grid_record.buy_state == 1 and not spot_grid_record.sell_state:  # 开仓
                            all_position_amount += spot_grid_record.position_amount
                            all_value += spot_grid_record.position_amount * spot_grid_record.buy_price

                        if spot_grid_record.sell_state == 1:  # 已平仓
                            all_realized_profit += spot_grid_record.realized_profit
                            all_sell_fee += spot_grid_record.sell_fee
                    spot_record.all_value = all_value
                    spot_record.all_position_amount = all_position_amount
                    spot_record.avg_buy_price = (all_value / all_position_amount) if all_position_amount != 0 else 0
                    spot_record.all_unrealized_profit = spot_record.all_position_amount * (
                            mark_price - spot_record.avg_buy_price)
                    spot_record.all_realized_profit = all_realized_profit
                    spot_record.all_sell_fee = all_sell_fee
                else:
                    if state == 'partially_filled':
                        pass
                    else:
                        # 是否超时，如果超时，撤销执行
                        time_difference = (datetime.now() - record.buy_time).total_seconds()
                        if time_difference > 30:
                            # 撤销限价单，删除订单
                            try:
                                cancel_spot_order_okx_test(symbol[:-5], record.sell_order_id)
                                record.sell_state = None
                                logger.info(
                                    f'卖出订单超时未成交,取消订单-symbol:{record.symbol}-order_id:{record.sell_order_id}', )

                            except OrderNotFound:
                                pass
                        else:
                            logger.info(
                                f"卖出订单尚未成交,重新查询-symbol:{record.symbol}-order_id:{record.sell_order_id}")
                session.commit()
                session.close()
                return

            if not record.buy_state:  # 买入未成交
                order = get_spot_order_okx_test(symbol[:-5], record.buy_order_id)
                state = order['info']['state']
                if state == 'filled':
                    logger.info(f"买入订单已成交-symbol:{record.symbol}-order_id:{record.buy_order_id}")
                    record.buy_amount = float(order['info']['accFillSz'])
                    record.buy_price = float(order['info']['avgPx'])
                    record.buy_fee = float(order['info']['fee'])
                    # record.position_amount = align_precision(record.buy_amount + record.buy_fee,symbol)
                    record.position_amount =record.buy_amount + record.buy_fee
                    record.buy_state = 1
                    session.commit()
                    spot_record = session.query(Spot).filter_by(symbol=symbol).first()
                    # 计算统计表
                    spot_grid_records = session.query(SpotGrid).filter_by(symbol=symbol).all()
                    all_value = 0
                    all_position_amount = 0
                    all_realized_profit = 0
                    all_buy_fee = 0
                    all_sell_fee = 0
                    for spot_grid_record in spot_grid_records:
                        if spot_grid_record.buy_state == 1 and not spot_grid_record.sell_state:  # 开仓
                            all_position_amount += spot_grid_record.position_amount
                            all_value += spot_grid_record.position_amount * spot_grid_record.buy_price
                            all_buy_fee += spot_grid_record.buy_fee * spot_grid_record.buy_price

                        if spot_grid_record.sell_state == 1:  # 已平仓
                            all_realized_profit += spot_grid_record.realized_profit
                            all_sell_fee += spot_grid_record.sell_fee
                    spot_record.all_value = all_value
                    spot_record.all_position_amount = all_position_amount
                    spot_record.avg_buy_price = all_value / all_position_amount
                    spot_record.all_unrealized_profit = all_position_amount * (
                            mark_price - spot_record.avg_buy_price)
                    spot_record.all_buy_fee = all_buy_fee

                else:
                    if state == 'partially_filled':
                        pass
                    else:
                        # 是否超时，如果超时，撤销执行
                        time_difference = (datetime.now() - record.buy_time).total_seconds()
                        if time_difference > 30:
                            # 撤销限价单，删除订单
                            try:
                                cancel_spot_order_okx_test(symbol[:-5], record.buy_order_id)
                                logger.info(
                                    f"买入订单超时未成交,取消订单-symbol:{record.symbol}-order_id:{record.buy_order_id}")
                                session.delete(record)
                            except OrderNotFound:
                                pass
                        else:
                            logger.info(
                                f"买入订单尚未成交,重新查询-symbol:{record.symbol}-order_id:{record.buy_order_id}")
                session.commit()
                session.close()
                return

            elif record.buy_state == 1:
                if record.num < 49:
                    if mark_price < record.buy_price:  # 如果价格下降
                        if record.down_price:
                            if mark_price < record.down_price:  # 如果继续下降则更新
                                record.down_price = mark_price
                            else:  # 如果回调了0.02%,则开仓买入另一仓
                                if mark_price >= record.down_price * (1 + 0.0002):
                                    spot_grid = SpotGrid()
                                    spot_grid.symbol = symbol
                                    spot_grid.num = record.num + 1
                                    spot_grid.buy_time = event_time
                                    spot_grid.realized_profit = 0
                                    spot_grid.buy_fee = 0
                                    spot_grid.sell_fee = 0
                                    spot_grid.buy_order_id = symbol[:-5] + data['data'][0]['ts']
                                    order = place_spot_order_okx_test(symbol[:-5], 'long', mark_price,
                                                                      base_amount=quota_amount / mark_price,
                                                                      cl_order_id=spot_grid.buy_order_id)
                                    logger.info(order)
                                    if not order or order['info']['sCode'] != '0':
                                        return
                                    session.add(spot_grid)
                        else:
                            if mark_price < record.buy_price * (1 - 0.0015):  # 如果当前没有记录，且降幅超过0.15%，则准备另开一仓
                                record.down_price = mark_price
                    else:
                        if record.up_price:
                            if mark_price > record.up_price:  # 如果继续上升则更新
                                record.up_price = mark_price
                            else:
                                if mark_price <= record.up_price * (1 - 0.0005):  # 如果回调了0.05%,则卖出该仓位
                                    record.sell_order_id = symbol[:-5] + data['data'][0]['ts']
                                    order = place_spot_order_okx_test(symbol[:-5], 'short', mark_price,
                                                                      base_amount=record.position_amount,
                                                                      cl_order_id=record.sell_order_id)
                                    logger.info(order)
                                    if not order or order['info']['sCode'] != '0':
                                        return
                                    record.sell_state = 0
                                    record.sell_time = event_time
                        else:
                            if mark_price > record.buy_price * (1 + 0.006):  # 如果当前没有记录，且增幅超过0.6%，则准备卖出
                                record.up_price = mark_price
                elif record.num == 49:
                    if mark_price < record.buy_price:  # 如果价格下降
                        if record.down_price:
                            if mark_price < record.down_price:  # 如果继续下降则更新
                                record.down_price = mark_price
                            else:  # 如果回调了0.5%,则开仓买入另一仓
                                if mark_price >= record.down_price * (1 + 0.005):
                                    spot_grid_1 = SpotGrid()
                                    spot_grid_1.num = record.num + 1
                                    spot_grid_1.symbol = symbol
                                    spot_grid_1.buy_time = event_time
                                    spot_grid_1.realized_profit = 0
                                    spot_grid_1.buy_fee = 0
                                    spot_grid_1.sell_fee = 0
                                    spot_grid_1.buy_order_id = symbol[:-5] + data['data'][0]['ts']
                                    session.add(spot_grid_1)
                                    spot_record = session.query(Spot).filter_by(symbol=symbol).first()
                                    order = place_spot_order_okx_test(symbol[:-5], 'long', mark_price,
                                                                      base_amount=spot_record.all_position_amount,
                                                                      cl_order_id=spot_grid_1.buy_order_id)
                                    logger.info(order)
                                    if not order or order['info']['sCode'] != '0':
                                        return
                                    logger.info(
                                        f":thumbs_up: 新买入订单-symbol:{spot_grid_1.symbol}-order_id:{spot_grid_1.buy_order_id}")
                        else:
                            # 查询均价
                            spot_record = session.query(Spot).filter_by(symbol=symbol).first()
                            if mark_price < spot_record.avg_buy_price * (1 - 0.05):  # 如果当前没有记录，且降幅超过5%，则准备另开一仓
                                record.down_price = mark_price
                    else:
                        if record.up_price:
                            if mark_price > record.up_price:  # 如果继续上升则更新
                                record.up_price = mark_price
                            else:
                                if mark_price <= record.up_price * (1 - 0.0005):  # 如果回调了0.05%,则卖出该仓位
                                    record.sell_order_id = symbol[:-5] + data['data'][0]['ts']
                                    order = place_spot_order_okx_test(symbol[:-5], 'short', mark_price,
                                                                      base_amount=record.buy_amount,
                                                                      cl_order_id=record.sell_order_id)
                                    logger.info(order)
                                    if not order or order['info']['sCode'] != '0':
                                        return
                                    logger.info(
                                        f":thumbs_up: 卖出订单尚已成交-symbol:{record.symbol}-order_id:{record.sell_order_id}")
                                    record.sell_state = 0
                                    record.sell_time = event_time
                        else:
                            if mark_price > record.buy_price * (1 + 0.006):  # 如果当前没有记录，且增幅超过0.6%，则准备卖出
                                record.up_price = mark_price
                elif record.num == 50:
                    if mark_price < record.buy_price:  # 如果价格下降
                        if record.down_price:
                            if mark_price < record.down_price:  # 如果继续下降则更新
                                record.down_price = mark_price
                            else:  # 如果回调了0.5%,则开仓买入另一仓
                                if mark_price >= record.down_price * (1 + 0.007):
                                    spot_grid_1 = SpotGrid()
                                    spot_grid_1.num = record.num + 1
                                    spot_grid_1.symbol = symbol
                                    spot_grid_1.buy_time = event_time
                                    spot_grid_1.realized_profit = 0
                                    spot_grid_1.buy_fee = 0
                                    spot_grid_1.sell_fee = 0
                                    spot_grid_1.buy_order_id = symbol[:-5] + data['data'][0]['ts']
                                    session.add(spot_grid_1)
                                    spot_record = session.query(Spot).filter_by(symbol=symbol, buy_state=1,
                                                                                sell_state=None).first()
                                    order = place_spot_order_okx_test(symbol[:-5], 'long', mark_price,
                                                                      base_amount=spot_record.all_position_amount,
                                                                      cl_order_id=spot_grid_1.buy_order_id)
                                    logger.info(order)
                                    if not order or order['info']['sCode'] != '0':
                                        return
                                    logger.info(
                                        f":thumbs_up: 新买入订单-symbol:{spot_grid_1.symbol}-order_id:{spot_grid_1.buy_order_id}")
                        else:
                            # 查询均价
                            spot_record = session.query(Spot).filter_by(symbol=symbol).first()
                            if mark_price < spot_record.avg_buy_price * (1 - 0.07):  # 如果当前没有记录，且降幅超过7%，则准备另开一仓
                                record.down_price = mark_price
                    else:
                        if record.up_price:
                            if mark_price > record.up_price:  # 如果继续上升则更新
                                record.up_price = mark_price
                            else:
                                if mark_price <= record.up_price * (1 - 0.001):  # 如果回调了0.1%,则卖出该仓位
                                    record.sell_order_id = symbol[:-5] + data['data'][0]['ts']
                                    order = place_spot_order_okx_test(symbol[:-5], 'short', mark_price,
                                                                      base_amount=record.buy_amount,
                                                                      cl_order_id=record.sell_order_id)
                                    logger.info(order)
                                    if not order or order['info']['sCode'] != '0':
                                        return

                                    logger.info(
                                        f":thumbs_up: 卖出订单尚已成交-symbol:{record.symbol}-order_id:{record.sell_order_id}")
                                    record.sell_state = 0
                                    record.sell_time = event_time
                        else:
                            if mark_price > record.buy_price * (1 + 0.012):  # 如果当前没有记录，且增幅超过0.6%，则准备卖出
                                record.up_price = mark_price
                elif record.num == 51:
                    if mark_price < record.buy_price:  # 如果价格下降
                        if record.down_price:
                            if mark_price < record.down_price:  # 如果继续下降则更新
                                record.down_price = mark_price
                            else:  # 如果回调了0.5%,则开仓买入另一仓
                                if mark_price >= record.down_price * (1 + 0.007):
                                    spot_grid_1 = SpotGrid()
                                    spot_grid_1.num = record.num + 1
                                    spot_grid_1.symbol = symbol
                                    spot_grid_1.buy_time = event_time
                                    spot_grid_1.realized_profit = 0
                                    spot_grid_1.buy_fee = 0
                                    spot_grid_1.sell_fee = 0
                                    spot_grid_1.buy_order_id = symbol[:-5] + data['data'][0]['ts']
                                    session.add(spot_grid_1)
                                    spot_record = session.query(Spot).filter_by(symbol=symbol, buy_state=1,
                                                                                sell_state=None).first()
                                    order = place_spot_order_okx_test(symbol[:-5], 'long', mark_price,
                                                                      base_amount=spot_record.all_position_amount,
                                                                      cl_order_id=spot_grid_1.buy_order_id)
                                    logger.info(order)
                                    if not order or order['info']['sCode'] != '0':
                                        return
                                    logger.info(
                                        f":thumbs_up: 新买入订单-symbol:{spot_grid_1.symbol}-order_id:{spot_grid_1.buy_order_id}")

                        else:
                            # 查询均价
                            spot_record = session.query(Spot).filter_by(symbol=symbol).first()
                            if mark_price < spot_record.avg_buy_price * (1 - 0.07):  # 如果当前没有记录，且降幅超过7%，则准备另开一仓
                                record.down_price = mark_price
                    else:
                        if record.up_price:
                            if mark_price > record.up_price:  # 如果继续上升则更新
                                record.up_price = mark_price
                            else:
                                if mark_price <= record.up_price * (1 - 0.001):  # 如果回调了0.1%,则卖出该仓位
                                    record.sell_order_id = symbol[:-5] + data['data'][0]['ts']
                                    order = place_spot_order_okx_test(symbol[:-5], 'short', mark_price,
                                                                      base_amount=record.buy_amount,
                                                                      cl_order_id=record.sell_order_id)
                                    if not order or order['info']['sCode'] != '0':
                                        return
                                    logger.info(
                                        f":thumbs_up: 新买入订单-symbol:{record.symbol}-order_id:{record.buy_order_id}")
                                    record.sell_state = 0
                                    record.sell_time = event_time
                        else:
                            if mark_price > record.buy_price * (1 + 0.012):  # 如果当前没有记录，且增幅超过0.6%，则准备卖出
                                record.up_price = mark_price
                elif record.num == 52:
                    if record.up_price:
                        if mark_price > record.up_price:  # 如果继续上升则更新
                            record.up_price = mark_price
                        else:
                            if mark_price <= record.up_price * (1 - 0.001):  # 如果回调了0.1%,则卖出该仓位
                                record.sell_order_id = symbol[:-5] + data['data'][0]['ts']
                                order = place_spot_order_okx_test(symbol[:-5], 'short', mark_price,
                                                                  base_amount=record.buy_amount,
                                                                  cl_order_id=record.sell_order_id)
                                logger.info(order)
                                if not order or order['info']['sCode'] != '0':
                                    return
                                logger.info(
                                    f":thumbs_up: 卖出订单尚已成交-symbol:{record.symbol}-order_id:{record.sell_order_id}")
                                record.sell_state = 0
                                record.sell_time = event_time
                    else:
                        if mark_price > record.buy_price * (1 + 0.012):  # 如果当前没有记录，且增幅超过0.6%，则准备卖出
                            record.up_price = mark_price
        session.commit()
        session.close()

market_map={}
async def main():
    connected = False
    symbols = [
        "ETH-USDT",
        "BTC-USDT",
        "BNB-USDT",
        "ADA-USDT",
        "DOGE-USDT",
        "MATIC-USDT",
        "SOL-USDT",
        "DOT-USDT",
        "OP-USDT",
        "ARB-USDT",
        "FIL-USDT",
        "AVAX-USDT",
        "NEAR-USDT",
        "SUI-USDT",
        "LTC-USDT",
        "SATS-USDT",
        "LINK-USDT",
        "SHIB-USDT",
    ]

    # argslist = []
    #
    # for symbol in symbols:
    #     argslist.append(dict(channel='tickers', instId=symbol))
    #     # precision_map[symbol] = get_market_info(symbol)['precision']['amount']
    #     market_map[symbol] = get_market_info(symbol)
    while not connected:
        try:
            url = "wss://wspap.okx.com:8443/ws/v5/public?brokerId=9999"
            async with websockets.connect(url, ping_interval=20, ping_timeout=60) as ws:
                subs = dict(
                    op='subscribe',
                    args=[
                        dict(channel='tickers', instId="ETH-USDT"),
                        dict(channel='tickers', instId="BTC-USDT"),
                        dict(channel='tickers', instId="BNB-USDT"),
                        dict(channel='tickers', instId="ADA-USDT"),
                        dict(channel='tickers', instId="DOGE-USDT"),
                        dict(channel='tickers', instId="MATIC-USDT"),
                        dict(channel='tickers', instId="SOL-USDT"),
                        # dict(channel='tickers', instId="DOT-USDT"),
                        dict(channel='tickers', instId="OP-USDT"),
                        dict(channel='tickers', instId="ARB-USDT"),
                        dict(channel='tickers', instId="FIL-USDT"),
                        dict(channel='tickers', instId="BCH-USDT"),
                        dict(channel='tickers', instId="AVAX-USDT"),
                        dict(channel='tickers', instId="NEAR-USDT"),
                        dict(channel='tickers', instId="SUI-USDT"),
                        dict(channel='tickers', instId="LTC-USDT"),

                        dict(channel='tickers', instId="SATS-USDT"),
                        dict(channel='tickers', instId="LINK-USDT"),
                        dict(channel='tickers', instId="SHIB-USDT"),
                    ]
                )
                await ws.send(json.dumps(subs))

                async for msg in ws:
                    msg = json.loads(msg)
                    if 'data' in msg:
                        process_kline(msg)
                connected = True  # 连接成功后设置为 True
        except ConnectionClosedError:
            logger.error("Connection closed unexpectedly. Reconnecting...")
            await asyncio.sleep(3)
            await main()
        except Exception as e:
            logger.error(e, exc_info=True)



if __name__ == '__main__':
    asyncio.run(main())
