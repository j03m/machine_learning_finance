import torch.nn as nn

# mine
# class LSTMModel(nn.Module):
#     def __init__(self, features, batch_size, hidden_dim, output_size, num_layers=1):
#         super(LSTMModel, self).__init__()
#         self.hidden_layer_size = hidden_dim
#         self.num_layers = num_layers
#         self.lstm = nn.LSTM(features, hidden_dim, num_layers, batch_first=True)
#         self.linear = nn.Linear(hidden_dim, output_size)
#         self.batch_size = batch_size
#
#     def forward(self, input_seq):
#         lstm_out, _ = self.lstm(input_seq)
#         predictions = self.linear(lstm_out[:, -1, :])
#         return predictions

# lstm model from: https://github.com/jinglescode/time-series-forecasting-pytorch.git
class LSTMModel(nn.Module):
    def __init__(self, features, batch_size, hidden_dim, output_size, num_layers=1, dropout=0.2):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.batch_size = batch_size
        self.linear_1 = nn.Linear(features, hidden_dim)
        self.relu = nn.ReLU()
        self.lstm = nn.LSTM(hidden_dim, hidden_size=self.hidden_dim, num_layers=num_layers,
                            batch_first=True)
        self.dropout = nn.Dropout(dropout)
        self.linear_2 = nn.Linear(num_layers * hidden_dim, output_size)

        self.init_weights()

    # can use defaults
    def init_weights(self):
        for name, param in self.lstm.named_parameters():
            if 'bias' in name:
                nn.init.constant_(param, 0.0)
            elif 'weight_ih' in name:
                nn.init.kaiming_normal_(param)
            elif 'weight_hh' in name:
                nn.init.orthogonal_(param)

    def forward(self, x):
        #batchsize = x.shape[0]

        # layer 1
        x = self.linear_1(x)
        x = self.relu(x)

        # LSTM layer
        lstm_out, (h_n, c_n) = self.lstm(x)

        # reshape output from hidden cell into [batch, features] for `linear_2`
        x = h_n.permute(1, 0, 2).reshape(self.batch_size, -1)

        # layer 2
        x = self.dropout(x)
        predictions = self.linear_2(x)
        return predictions