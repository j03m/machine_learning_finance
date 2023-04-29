import torch as th
from typing import NamedTuple, Tuple
import numpy as np
from sb3_contrib.ppo_recurrent.policies import MlpLstmPolicy

class RNNStates(NamedTuple):
    pi: Tuple[th.Tensor, ...]
    vf: Tuple[th.Tensor, ...]


class CustomActorCriticPolicy(MlpLstmPolicy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_actions = None
        self.custom_actions_index = 0

    def set_custom_actions(self, custom_actions):
        self.custom_actions = custom_actions
        self.custom_actions_index = 0

    def forward(
            self,
            obs,
            lstm_states,
            episode_starts,
            deterministic=False):
        """
        Forward pass in all the networks (actor and critic)

        :param obs: Observation. Observation
        :param lstm_states: The last hidden and memory states for the LSTM.
        :param episode_starts: Whether the observations correspond to new episodes
            or not (we reset the lstm states in that case).
        :param deterministic: Whether to sample or use deterministic actions
        :return: action, value and log probability of the action
        """
        # Preprocess the observation if needed
        features = self.extract_features(obs)
        if self.share_features_extractor:
            pi_features = vf_features = features  # alis
        else:
            pi_features, vf_features = features
        # latent_pi, latent_vf = self.mlp_extractor(features)
        latent_pi, lstm_states_pi = self._process_sequence(pi_features, lstm_states.pi, episode_starts, self.lstm_actor)
        if self.lstm_critic is not None:
            latent_vf, lstm_states_vf = self._process_sequence(vf_features, lstm_states.vf, episode_starts,
                                                               self.lstm_critic)
        elif self.shared_lstm:
            # Re-use LSTM features but do not backpropagate
            latent_vf = latent_pi.detach()
            lstm_states_vf = (lstm_states_pi[0].detach(), lstm_states_pi[1].detach())
        else:
            # Critic only has a feedforward network
            latent_vf = self.critic(vf_features)
            lstm_states_vf = lstm_states_pi

        latent_pi = self.mlp_extractor.forward_actor(latent_pi)
        latent_vf = self.mlp_extractor.forward_critic(latent_vf)

        # Evaluate the values for the given observations
        values = self.value_net(latent_vf)
        distribution = self._get_action_dist_from_latent(latent_pi)
        if self.custom_actions is not None:
            # Retrieve the next custom action
            custom_action = self.custom_actions[self.custom_actions_index]
            self.custom_actions_index += 1
            if self.custom_actions_index >= len(self.custom_actions):
                self.custom_actions_index = 0

            actions = np.array([custom_action])
            actions = th.tensor(actions, dtype=th.float32, device=self.device)

            # Compute the log probabilities of the custom actions
            log_prob = distribution.log_prob(th.tensor(actions, dtype=th.float32, device=self.device))
        else:
            # If no custom actions are provided, use the actions generated by the actor network
            actions = distribution.get_actions(deterministic=deterministic)
            log_prob = distribution.log_prob(actions)
        return actions, values, log_prob, RNNStates(lstm_states_pi, lstm_states_vf)