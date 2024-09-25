#!/bin/bash

# Check if at least one argument is provided
if [ -z "$1" ]; then
    echo "No list file supplied."
    exit 1
fi

python scripts/cache-prices.py "--symbol-file=$1" &&
python scripts/cache-rates.py &&
python scripts/cache-fundementals.py "--symbol-file=$1" &&
python scripts/create-final-data-set.py "--symbol-file=$1"