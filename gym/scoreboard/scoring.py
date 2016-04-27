"""This is the actual code we use to score people's solutions
server-side. The interfaces here are not yet stable, but we include
them so that people can reproduce our scoring calculations
independently.

We correspondly do not currently import this module.
"""

import numpy as np
import requests

import gym

def score_from_remote(url):
    result = requests.get(url)
    parsed = result.json()
    episode_lengths = parsed['episode_lengths']
    episode_rewards = parsed['episode_rewards']
    timestamps = parsed['timestamps']
    env_id = parsed['env_id']

    spec = gym.spec(env_id)
    return score_from_merged(episode_lengths, episode_rewards, timestamps, spec.trials, spec.reward_threshold)

def score_from_merged(episode_lengths, episode_rewards, timestamps, trials, reward_threshold):
    """Method to calculate the score from merged monitor files.
    """
    # Make sure everything is a float -- no pesky ints.
    episode_rewards = np.array(episode_rewards, dtype='float64')
    episode_t_value = timestep_t_value = mean = error = time_in_seconds = None

    if len(timestamps) > 2:
        # This is: time from the first *step* to the last *step*.
        time_in_seconds = timestamps[-1] - timestamps[0]
    if len(episode_rewards) >= trials:
        means = running_mean(episode_rewards, trials)
        if reward_threshold is not None:
            # Compute t-value by finding the first index above the
            # threshold. It comes out as a singleton tuple.
            (indexes_above_threshold, ) = np.where(means > reward_threshold)
            if len(indexes_above_threshold) > 0:
                # Grab the first episode index that is above the threshold value
                episode_t_value = indexes_above_threshold[0]

                # Find timestep corresponding to this episode
                cumulative_timesteps = np.cumsum(np.insert(episode_lengths, 0, 0))
                # Convert that into timesteps
                timestep_t_value = cumulative_timesteps[episode_t_value]

        # Find the window with the best mean
        best_idx = np.argmax(means)
        best_rewards = episode_rewards[best_idx:best_idx+trials]
        mean = np.mean(best_rewards)
        error = np.std(best_rewards) / (np.sqrt(trials) - 1)
    return {
        'episode_t_value': episode_t_value,
        'timestep_t_value': timestep_t_value,
        'mean': mean,
        'error': error,
        'number_episodes': len(episode_rewards),
        'number_timesteps': sum(episode_lengths),
        'time_in_seconds': time_in_seconds,
    }

def running_mean(x, N):
    x = np.array(x, dtype='float64')
    cumsum = np.cumsum(np.insert(x, 0, 0))
    return (cumsum[N:] - cumsum[:-N]) / N

def compute_graph_stats(episode_lengths, episode_rewards, timestamps, buckets):
    """Method to compute the aggregates for the graphs."""
    # Not a dependency of OpenAI Gym generally.
    import scipy

    num_episodes = len(episode_lengths)

    episode_rewards = np.array(episode_rewards)
    episode_lengths = np.array(episode_lengths)

    # The index of the start of each episode
    x_timestep = np.cumsum(np.insert(episode_lengths, 0, 0))[:-1]
    assert len(x_timestep) == num_episodes

    # Nothing to compute here
    x_timestamp = timestamps

    # The index of each episode
    x_episode = range(num_episodes)

    # Calculate the appropriate x/y statistics
    x_timestep_y_reward = scipy.stats.binned_statistic(x_timestep, episode_rewards, 'median', buckets)
    x_timestep_y_length = scipy.stats.binned_statistic(x_timestep, episode_lengths, 'median', buckets)

    x_episode_y_reward = scipy.stats.binned_statistic(x_episode, episode_rewards, 'median', buckets)
    x_episode_y_length = scipy.stats.binned_statistic(x_episode, episode_lengths, 'median', buckets)

    x_timestamp_y_reward = scipy.stats.binned_statistic(x_timestamp, episode_rewards, 'median', buckets)
    x_timestamp_y_length = scipy.stats.binned_statistic(x_timestamp, episode_lengths, 'median', buckets)


    return {
        'x_timestep_y_reward': graphable_binned_statistic(x_timestep_y_reward),
        'x_timestep_y_length': graphable_binned_statistic(x_timestep_y_length),
        'x_episode_y_reward': graphable_binned_statistic(x_episode_y_reward),
        'x_episode_y_length': graphable_binned_statistic(x_episode_y_length),
        'x_timestamp_y_length': graphable_binned_statistic(x_timestamp_y_length),
        'x_timestamp_y_length': graphable_binned_statistic(x_timestamp_y_length),
    }

def graphable_binned_statistic(binned):
    x = running_mean(binned.bin_edges, 2)
    y = binned.statistic
    assert len(x) == len(y)

    # Get rid of nasty NaNs
    valid = np.logical_not(np.isnan(x)) & np.logical_not(np.isnan(y))
    x = x[valid]
    y = y[valid]

    return {
        'x': x,
        'y': y,
    }