#!/usr/bin/env python3
import argparse
import warnings
import random
import time
import pandas as pd

from machine_learning_finance import make_env_for, partial_test, partial_train, download_ticker_list

# filter out UserWarning messages
warnings.filterwarnings("ignore", category=UserWarning)

MODEL_PPO = 0
MODEL_RECURRENT = 1

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("-s", "--symbols", help="Symbols to use, separated by comma")
parser.add_argument("-t", "--tail", type=int, default=2500, help="Tail size (default: 2500)")
parser.add_argument("-r", "--train", action="store_true", help="Enable partial training")
parser.add_argument("-e", "--test", action="store_true", help="Enable partial testing")
parser.add_argument("-p", "--steps", type=int, default=25000000, help="Number of steps (default: 25000000)")
parser.add_argument("-c", "--create", action="store_true", help="Create new environment")
parser.add_argument("-o", "--output-dir", default="./backtests", help="Output directory (default: ./backtests)")
parser.add_argument("-rs", "--random-spys", type=int, default=None, help="Number of random stocks to select from SPY")
parser.add_argument("-rt", "--random-tickers", type=int, default=None,
                    help="Number of random tickers to select from train_tickers files")
parser.add_argument("-ft", "--file-tickers", action="store_true", default=False,
                    help="Load data from tickers.csv (use data cacher to seed data)")
parser.add_argument("-uc", "--use-cache", action="store_true", default=False,
                    help="Load data from tickers.csv (use data cacher to seed data)")
parser.add_argument("-u", "--curriculum", type=int, choices=[1, 2, 3], default=2, help="Curriculum level (default: 2)")
parser.add_argument("-m", "--model", type=int, choices=[0, 1], default=1, help="What model to use")



args = parser.parse_args()

def rando_tickers(num):
    dfs = [pd.read_csv(f"./data/training_tickers{i}.csv") for i in range(1, 4)]
    df = pd.concat(dfs)
    tickers = df['TICKERS'].tolist()

    # Select num random tickers from the list
    random_tickers = random.sample(tickers, num)

    return random_tickers


def rando_spys(num):
    sp_assets = pd.read_html(
        'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
    assets = sp_assets['Symbol'].str.replace('.', '-').tolist()

    # Select num random symbols from SPY
    random_symbols = random.sample(assets, num)

    return random_symbols

symbols = []
if not args.file_tickers:
    if args.symbols is not None:
        symbols += args.symbols.split(',')

    if args.random_spys is not None:
        symbols += rando_spys(args.random_spys)

    if args.random_tickers is not None:
        symbols += rando_tickers(args.random_tickers)
    symbols = list(set(symbols))
    if len(symbols)==0:
        print("No --symbols were supplied!")
        exit(-1)
    if not args.use_cache:
        download_ticker_list(symbols)
else:
    # assumes data is pre cached with cache_data.py
    symbols = pd.read_csv("./data/symbols.csv")["Symbols"]

if args.train:
    for symbol in symbols:
        print("training:", symbol)
        try:
            time.sleep(0.25)
            env = make_env_for(symbol, args.curriculum, args.tail, "file")
            partial_train(env, args.steps, args.create, args.model)
            env.ledger.to_csv(f"{args.output_dir}/env_{symbol}_train.csv")
        except Exception as e:
            print(e)

if args.test:
    for symbol in symbols:
        print("testing:", symbol)
        try:
            time.sleep(0.25)
            env = make_env_for(symbol, args.curriculum, args.tail, "file")
            partial_test(env)
            env.ledger.to_csv(f"{args.output_dir}/env_{symbol}_test.csv")
        except Exception as e:
            print(e)
