import torch
from torch.utils.data import Dataset
from torch.nn.utils.rnn import pad_sequence
import pandas as pd


class BasicPandasDataset(Dataset):
    """Dataset wrapping data and target variables in a pandas dataframe."""

    def __init__(self, dataframe, feature_columns, target_column):
        """
        Args:
            dataframe (DataFrame): A pandas dataframe.
            feature_columns (list of str): The names of the columns in the dataframe to be used as features.
            target_column (str): The name of the column in the dataframe to be used as the target variable.
        """
        self.dataframe = dataframe
        self.feature_columns = feature_columns
        self.target_column = target_column

    def __len__(self):
        return len(self.dataframe)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()

        features = self.dataframe.iloc[idx][self.feature_columns].values
        target = self.dataframe.iloc[idx][self.target_column]
        sample = {'features': torch.from_numpy(features).float(), 'target': torch.tensor(target).float()}

        return sample


def sliding_time_window(time_series, input_window, output_window):
    max_index = (len(time_series) - (input_window + output_window))

    # create a sliding window of sequences each predicting the next point.
    # if we have 4000 points, and we want 100 point predictions, we can have 3900 of these total
    # thus time_series.size(0) (the length) - iw
    # temp would end up being 3900 groups of (2, input_window)
    # first of the 2 groups is the input input_window and the 2nd would be the expected output window
    # even tho we may predict a subset of input_window in output_window we assume it's larger here
    # the last input are the number of features time_series.size(1)
    inputs = []
    outputs = []
    for i in range(max_index):
        inputs.append(time_series[i:i + input_window])
        outputs.append(time_series[i + input_window:i + input_window + output_window])

    input_windows = pad_sequence(inputs, batch_first=True)
    output_windows = pad_sequence(outputs, batch_first=True)

    # Stack to create a single tensor with separate dimensions for input and output
    return input_windows, output_windows


def derive_target_prices(dataframe, derivation_column, derivations, input_window, input_windows):
    prices = dataframe[derivation_column].values
    final_derivations = []
    for window in range(0, len(input_windows)):
        # the last price in the input window (probably could have sliced prices into N windows as well but)
        last_price_in_window = prices[window + input_window]
        final_derivations.append([])
        for derivation in derivations:
            # get the price N prices ahead of the end of the input window
            price = prices[window + input_window + derivation]
            profit = price - last_price_in_window
            final_derivations[window].append(profit)
    return final_derivations


class SlidingWindowPandasDataset(Dataset):

    def __init__(self, dataframe, feature_columns, input_window, output_window):
        """
        Args:
            dataframe (DataFrame): A pandas dataframe.
            feature_columns (list of str): The names of the columns in the dataframe to be used as features.
            input_window (int):  the size of the input window
            output_window (int): the size of the output window

        """
        features = dataframe[feature_columns].values
        self.input_windows, self.output_windows = sliding_time_window(torch.tensor(features), input_window,
                                                                      output_window)
        assert (len(self.input_windows) == len(self.output_windows))

    def __len__(self):
        return len(self.input_windows)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()
        return self.input_windows[idx].float(), self.output_windows[idx].float()


class SlidingWindowDerivedOutputDataset(SlidingWindowPandasDataset):
    def __init__(self, dataframe, feature_columns, input_window, derivations, derivation_column):
        derivations = sorted(derivations)
        output_window = max(derivations)

        # Correctly slice rows of the dataframe to include the necessary range for input and output windows
        # i don't remember why we do this
        # required_rows = len(dataframe) - output_window + 1
        # truncated_dataframe = dataframe.iloc[:required_rows]

        super().__init__(dataframe, feature_columns, input_window, output_window)
        derive_target_prices(dataframe, derivation_column, derivations, input_window, self.input_windows)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()
        return self.input_windows[idx].float(), torch.tensor(self.derivations[idx]).float()


class MultiSymbolStreamingSlidingWindowDerivedOutputDataset(Dataset):
    def __init__(self, data_path, ticker_list, feature_columns, input_window, derivations, derivation_column):
        self.derivations = sorted(derivations)
        self.derived_targets = []
        self.data_path = data_path
        self.output_window = max(derivations)
        self.input_window = input_window
        self.ticker_list = ticker_list
        self.derivation_column = derivation_column
        self.input_windows = []
        self.current_ticker = 0
        self.total_tickers = len(ticker_list)
        self.feature_columns = feature_columns
        self.length = None
        self.calculate_length()
        self.append_data(0)

    def calculate_length(self):
        self.length = 0
        for ticker in self.ticker_list:
            try:
                df = pd.read_csv(f"{self.data_path}/{ticker}_diffs.csv", index_col='Date', parse_dates=True)
            except FileNotFoundError:
                print(f"{ticker} is not found, skipping")
                continue
            if len(df) < self.input_window + self.output_window:
                print(f"{ticker} not enough data, skipping")
                continue
            max_index = (len(df) - (self.input_window + self.output_window))
            self.length += max_index

    def get_current_ticker(self):
        return self.ticker_list[self.current_ticker]

    def __len__(self):
        return self.length

    def append_data(self, idx):
        # get the next ticker and load it into input windows
        ticker = self.ticker_list[self.current_ticker]
        self.current_ticker += 1
        try:
            df = pd.read_csv(f"{self.data_path}/{ticker}_diffs.csv", index_col='Date', parse_dates=True)
        except FileNotFoundError:
            print(f"{ticker} is not found, skipping")
            return self.__getitem__(idx)

        if len(df) < self.input_window + self.output_window:
            # not enough data skip the symbol
            print(f"{ticker} not enough data, skipping")
            return self.__getitem__(idx)

        features = df[self.feature_columns].values
        input_windows, _ = sliding_time_window(torch.tensor(features), self.input_window,
                                               self.output_window)
        derivations = derive_target_prices(df, self.derivation_column, self.derivations, self.input_window,
                                           input_windows)
        self.input_windows.extend(input_windows)
        self.derived_targets.extend(derivations)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            raise Exception("Unsupported!")
        available_windows = len(self.input_windows)
        if idx >= available_windows:
            # load more data
            if self.current_ticker < self.total_tickers:
                self.append_data(idx)
            else:
                raise Exception("Should not have happened...")
        return self.input_windows[idx].float(), torch.tensor(self.derived_targets[idx]).float()
