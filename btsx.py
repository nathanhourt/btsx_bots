import urllib2
import json
import requests
from mylog import logger
import time

log = logger.log

class BTSX():
    CNY_PRECISION = 10000.0
    USD_PRECISION = 10000.0
    BTSX_PRECISION = 100000.0
    
    def __init__(self, user, password, port):
        self.url = "http://" + user + ":" + password + "@localhost:" + str(port) + "/rpc"
        log("Initializing with URL:  " + self.url)

    def request(self, method, *args):
        payload = {
            "method": method,
            "params": list(*args),
            "jsonrpc": "2.0",
            "id": 0,
        }
        headers = {
          'content-type': 'application/json',
          'Authorization': "Basic YTph"
        }
        response = requests.post(self.url, data=json.dumps(payload), headers=headers)
        return response

    def get_median(self, asset):
        response = self.request("blockchain_get_feeds_for_asset", [asset])
        feeds = response.json()["result"]
        return feeds[len(feeds)-1]["median_price"]

    def submit_bid(self, account, amount, quote, price, base):
        response = self.request("bid", [account, amount, quote, price, base])
        if response.status_code != 200:
            log("%s submitted a bid" % account)
            log(response.json())
            return False
        else:
            return response.json()
    def submit_ask(self, account, amount, quote, price, base):
        response = self.request("ask", [account, amount, quote, price, base])
        if response.status_code != 200:
            log("%s submitted an ask" % account())
            log(response.json())
            return False
        else:
            return response.json()

    def get_lowest_ask(self, asset1, asset2):
        response = self.request("blockchain_market_order_book", [asset1, asset2])
        amount = float(response.json()["result"][0][0]["market_index"]["order_price"]["ratio"])
        return amount 
        
    def get_balance(self, account, asset):

        asset_id = self.get_asset_id(asset) 

        response = self.request("wallet_account_balance", [account, asset])
        if not response.json():
            log("Error in get_balance: %s", response["_content"]["message"])
            return 0
        if "result" not in response.json() or response.json()["result"] == None:
            return 0

        asset_array = response.json()["result"][0][1]
        amount = 0
        for item in asset_array:
            if item[0] == asset_id:
                amount = item[1]
                return amount / self.get_precision(asset)
        return 0

    def cancel_bids_less_than(self, account, base, quote, price):
        cancel_args = self.get_bids_less_than(account, base, quote, price)[0]
        response = self.request("batch", ["wallet_market_cancel_order", cancel_args])
        return cancel_args

    def get_bids_less_than(self, account, base, quote, price):
        response = self.request("wallet_market_order_list", [base, quote, -1, account])
        order_ids = []
        quote_shares = 0
        if "result" not in response.json() or response.json()["result"] == None:
            return [[], 0]
        for pair in response.json()["result"]:
            order_id = pair[0]
            item = pair[1]
            if item["type"] == "bid_order":
                if float(item["market_index"]["order_price"]["ratio"])* (self.BTSX_PRECISION / self.USD_PRECISION) < price:
                    order_ids.append(order_id)
                    quote_shares += int(item["state"]["balance"])
                    log("%s canceled an order: %s" % (account, str(item)))
        cancel_args = [item for item in order_ids]
        return [cancel_args, float(quote_shares) / self.USD_PRECISION]

    def cancel_bids_out_of_range(self, account, base, quote, price, tolerance):
        cancel_args = self.get_bids_out_of_range(account, base, quote, price, tolerance)[0]
        response = self.get_bids_out_of_range(account, base, quote, price, tolerance)
        return cancel_args

    def get_bids_out_of_range(self, account, base, quote, price, tolerance):
        response = self.request("wallet_market_order_list", [base, quote, -1, account])
        order_ids = []
        quote_shares = 0
        if "result" not in response or response["result"] == None:
           return [[], 0]
        for pair in response.json()["result"]:
            order_id = pair[0]
            item = pair[1]
            if item["type"] == "bid_order":
                if abs(price - float(item["market_index"]["order_price"]["ratio"]) * (self.BTSX_PRECISION / self.USD_PRECISION)) > tolerance:
                    order_ids.append(order_id)
                    quote_shares += int(item["state"]["balance"])
                    log("%s canceled an order: %s" % (account, str(item)))
        cancel_args = [item for item in order_ids]
        return [cancel_args, float(quote_shares) / self.USD_PRECISION]

    def cancel_asks_out_of_range(self, account, base, quote, price, tolerance):
        cancel_args = self.get_asks_out_of_range(account, base, quote, price, tolerance)[0]
        response = self.request("batch", ["wallet_market_cancel_order", cancel_args])
        return cancel_args

    def get_asks_out_of_range(self, account, base, quote, price, tolerance):
        response = self.request("wallet_market_order_list", [base, quote, -1, account]).json()
        order_ids = []
        base_shares = 0
        if "result" not in response or response["result"] == None:
           return [[], 0]
        for pair in response["result"]:
            order_id = pair[0]
            item = pair[1]
            if item["type"] == "ask_order":
                if abs(price - float(item["market_index"]["order_price"]["ratio"]) * (self.BTSX_PRECISION / self.USD_PRECISION)) > tolerance:
                    order_ids.append(order_id)
                    base_shares += int(item["state"]["balance"])
        cancel_args = [item for item in order_ids]
        return [cancel_args, base_shares / self.BTSX_PRECISION]

    def cancel_all_orders(self, account, base, quote):
        cancel_args = self.get_all_orders(account, base, quote)
        response = self.request("batch", ["wallet_market_cancel_order", cancel_args])
        return cancel_args

    def get_all_orders(self, account, base, quote):
        response = self.request("wallet_market_order_list", [base, quote, -1, account])
        order_ids = []
        print response.json()
        if "result" in response.json():
           for item in response.json()["result"]:
               order_ids.append(item["market_index"]["owner"])
           cancel_args = [item for item in order_ids]
           return cancel_args
        return

    def get_last_fill (self, base, quote):
        last_fill = -1
        response = self.request("blockchain_market_order_history", [quote, base, 0, 1])
        for order in response.json()["result"]:
            last_fill = float(order["ask_price"]["ratio"]) 
        return last_fill


    def wait_for_block(self):
        response = self.request("get_info", [])
        blocknum = response.json()["result"]["blockchain_head_block_num"]
        while True:
            time.sleep(0.1)            
            response = self.request("get_info", [])
            blocknum2 = response.json()["result"]["blockchain_head_block_num"]
            if blocknum2 != blocknum:
                return

    def get_precision(self, asset):
        response = self.request("blockchain_get_asset", [asset])
        return response.json()["result"]["precision"]

    def get_asset_id(self, asset):
        response = self.request("blockchain_get_asset", [asset])
        return response.json()["result"]["id"]

