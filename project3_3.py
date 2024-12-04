# -*- coding: utf-8 -*-
"""project3_3.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1-bXRvfYv92NP8RyuM6tFOyA2J086fBS-
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
LW=5 # linewidth
MS=10 # markersize

def resample(Nsamples, samples, weights):
    """Generate *Nsamples* samples from an empirical distribution defined by *samples* and *weights*

    Inputs
    ------
    Nsamples: integer, number of samples to generate
    samples: (N, d) array of N samples of dimension d that form the empirical distribution
    weights: (N, ) array of N weights

    Returns
    --------
    samples_out: (Nsamples, d) new samples
    weights_out: (Nsamples, ) new weights equal to 1 / N
    """

    N = samples.shape[0]  # get number of points that make up the empirical distribution
    rr = np.arange(N) # get an ordered set of numbers from 0 to N-1

    # Randomly choose the integers (with replacement) between 0 to N-1 with probabilities given by the weights
    samp_inds = np.random.choice(rr, Nsamples, p=weights)

    # subselect the samples chosen
    samples_out = samples[samp_inds, :]

    # return uniform weights
    weights_out = np.ones((Nsamples))/Nsamples
    return samples_out, weights_out

def compute_mean_std(samples, weights):
    """Compute the mean and standard deviation of multiple empirical distirbution.

    Inputs
    ------
    samples: (N, d, m) array of samples defining the empirical distribution
    weights: (N, m) array of weights

    Returns
    -------
    means: (m, d) array of means
    stds: (m, d) array of standard deviations

    Notes
    -----
    m is the number of empirical distributions
    """

    N, d, m = samples.shape
    means = np.zeros((m, d))
    stds = np.zeros((m, d))
    for ii in range(m):
        means[ii, :] = np.dot(weights[:, ii], samples[:, :, ii])
        stds[ii, :] = np.sqrt(np.dot(weights[:, ii], (samples[:, :, ii] - np.tile(means[ii, :], (N, 1)))**2))
    return means, stds

def step(proc_cov, meas_cov, prop, proppdf, current_samples, current_weights, likelihood, data, propagator):
    """
    Propagate a particle filter

    Inputs
    --------
    prop            - proposal function (current_state, data)
    proppdf         - proposal function logpdf
    current_samples - ensemble of samples
    current_weights - ensemble of weights
    likelihood      - function to evaluate the log likelihood (samples, data)
    data            - Observation
    propagator      - dynamics logpdf

    @returns samples and weights after assimilating the data
    """
    #new_samples = np.zeros(current_samples.shape)
    #new_weights = np.zeros(current_weights.shape)
    new_samples = prop(proc_cov, meas_cov, current_samples, data)
    new_weights = likelihood(proc_cov, meas_cov, new_samples, data) + propagator(proc_cov, meas_cov, new_samples, current_samples) - \
                            proppdf(proc_cov, meas_cov, new_samples, current_samples, data)
    # print("Likeihood: ",likelihood(proc_cov, meas_cov, new_samples, data))
    # print("Propagator: ",propagator(proc_cov, meas_cov,new_samples, current_samples))
    # print("Proppdf: ",proppdf(proc_cov, meas_cov, new_samples, current_samples, data))
    new_weights = np.exp(new_weights) * current_weights
    new_weights = new_weights / np.sum(new_weights)
    return new_samples, new_weights

def dynamics_jacobian(current_state, dt=0.01):
    """Jacobian of the pendulum dynamics."""
    A = np.array([
        [1, dt],
        [-dt * 9.81 * np.cos(current_state[0]), 1]
    ])
    return A

def observation_jacobian(current_state):
    """Jacobian of the observation model."""
    H = np.array([[np.cos(current_state[0]), 0]])
    return H

def ekf_proposal(proc_cov, meas_cov, current_state, data, dt=0.01):
    """EKF proposal function for the particle filter."""
    n_particles = current_state.shape[0]
    dim = current_state.shape[1]

    new_samples = np.zeros_like(current_state)

    # Process and observation noise covariance
    Q = proc_cov
    R = meas_cov
    for i in range(n_particles):
        # Current particle
        x_prev = current_state[i]

        # Prediction step
        A = dynamics_jacobian(x_prev, dt)
        x_pred = pendulum_dyn(x_prev,dt)
        pred_cov = np.dot(A, np.dot(prior_cov, A.T)) + Q
        P_pred = np.dot(A, Q).dot(A.T) + Q

        # Update step
        H = observation_jacobian(x_pred)
        z_pred = observe(x_pred)
        S = np.dot(H, P_pred).dot(H.T) + R
        K = np.dot(P_pred, H.T).dot(np.linalg.inv(S))  # Kalman gain

        # Correct state with observation
        z_actual = data
        x_update = x_pred + np.dot(K, (z_actual - z_pred))

        # Update covariance (optional for proposal, but needed for logpdf)
        P_update = P_pred - np.dot(K, H).dot(P_pred)

        # Sample from the updated Gaussian proposal
        new_samples[i] = x_update + np.random.multivariate_normal(np.zeros(dim), P_update)


    return new_samples

def ekf_proposal_logpdf(proc_cov, meas_cov, current, previous, data, dt=0.01):
    """Log PDF of EKF proposal."""

    n_particles, state_dim = current.shape
    logpdf_values = np.zeros(n_particles)

    Q = proc_cov
    R = meas_cov

    for i in range(n_particles):
        # Extract particle state
        x_prev = previous[i]
        x_prop = current[i]

        # Dynamics Jacobian
        A = dynamics_jacobian(x_prev, dt)

        # Predicted state and covariance
        mu_pred = pendulum_dyn(x_prev, dt)
        cov_pred = A @ Q @ A.T + Q

        # Observation Jacobian
        H = observation_jacobian(mu_pred)

        # Predicted observation
        z_pred = observe(mu_pred)
        S = H @ cov_pred @ H.T + R
        K = cov_pred @ H.T @ np.linalg.inv(S)

        # Update mean and covariance
        z_actual = data[i] if len(data) > 1 else data
        mu_proposal = mu_pred + K @ (z_actual - z_pred)
        Sigma_proposal = cov_pred - K @ H @ cov_pred

        # Log PDF computation
        diff = x_prop - mu_proposal
        log_det = np.linalg.slogdet(Sigma_proposal)[1]
        inv_Sigma = np.linalg.inv(Sigma_proposal)
        logpdf_values[i] = -0.5 * (diff.T @ inv_Sigma @ diff) - 0.5 * log_det - 0.5 * state_dim * np.log(2 * np.pi)
    return logpdf_values

def particle_filter(proc_cov, meas_cov, data, prior_mean, prior_cov,
                    prop, proppdf, likelihood, propagator,
                    nsamples=1000, resampling_threshold_frac=0.1):
    """Particle Filter

    Inputs
    -------
    data: (nsteps, m) array of data points, N is the time index, m is the dimensionality of the data
    prior_mean: (d), prior mean
    prior_cov: (d, d), prior mean
    Nsamples: integer, number of samples in the empirical distribution
    resampling_threshold_frac: float between 0 and 1 indicating to resample when effective sample size below frac of nsamples

    Returns
    -------
    samples: (nsamples, d, nsteps)
    weights: (nsamples, nsteps)
    eff: (nsamples), effective sample size

    Notes
    -----
    For documentation of prop, proppdf, likelihood, and propagator -- see the step function
    """

    d = prior_mean.shape[0]
    nsteps = data.shape[0]

    # Allocate memory
    samples = np.zeros((nsamples, d, nsteps+1))
    weights = np.zeros((nsamples, nsteps+1))
    eff = np.zeros((nsteps+1)) # keep track of effective sample size at each step


    # Generate initial samples from the prior
    L = np.linalg.cholesky(prior_cov)
    samples[:, :, 0] = np.tile(prior_mean, (nsamples, 1))+ np.dot(L, np.random.randn(d, nsamples)).T
    weights[:, 0] = 1.0 / nsamples # all weights are equal because of independent sampling from prior
    eff[0] = nsamples

    resamp_threshold = int(nsamples * resampling_threshold_frac)

    for ii in range(1, nsteps+1):
        samples[:, :, ii], weights[:, ii] = step(proc_cov, meas_cov, prop,  proppdf, samples[:, :, ii-1], weights[:, ii-1],
                                                 likelihood, data[ii-1, :], propagator)
        # compute the effective sample size
        eff[ii] = 1.0 / np.sum(weights[:, ii]**2)

        # if ii % 50 == 0:
        #     print("eff = ", ii, eff[ii])

        # resample if effective sample size is below threshold
        if eff[ii] < resamp_threshold:
            samples[:, :, ii], weights[:, ii] = resample(nsamples, samples[:, :, ii], weights[:, ii])


    return samples, weights, eff

def pendulum_dyn(current_state, dt=0.1):
    """Pendulum dynamics

    Inputs
    ------
    Current_state : either (2,) or (N, 2) for vectorized input
    """
    if current_state.ndim == 1:
        next_state = np.zeros((2))
        next_state[0] = current_state[0] + dt * current_state[1]
        next_state[1] = current_state[1] - dt * 9.81 * np.sin(current_state[0])
    else: # multiple inputs
        next_state = np.zeros(current_state.shape)
        next_state[:, 0] = current_state[:, 0] + dt * current_state[:, 1]
        next_state[:, 1] = current_state[:, 1] - dt * 9.81 * np.sin(current_state[:, 0])
    return next_state

def observe(current_state):
    if current_state.ndim == 1:
        out = np.zeros((1))
        out[0] = np.sin(current_state[0])
    else:
        out = np.zeros((current_state.shape[0], 1))
        out[:, 0] = np.sin(current_state[:, 0])
    return out

x0 = np.array([1.5, 0])
dt = 0.01
Nsteps = 100
true = np.zeros((Nsteps, 2))
true[0, :] = x0
times = np.arange(0, Nsteps*dt, dt)
data = np.zeros((Nsteps-1, 1))
on_obs = 0
delta = 10 # 5,10,20,40
obs_freq = delta
obs_ind = np.arange(obs_freq, Nsteps, obs_freq)
Q = np.array([[3.33e-9, 5.0e-7],[5.0e-7, 1.0e-4]])
R = 1
prior_mean = np.array([1.5,0])
prior_cov = np.eye(2) # identity covariance
for ii in range(1, Nsteps):
    true[ii, :] = pendulum_dyn(true[ii-1, :],dt=dt)
    if on_obs < obs_ind.shape[0] and ii == obs_ind[on_obs]:
        data[ii-1] = observe(true[ii, :]) + np.random.randn()*R
        on_obs += 1

v_data = []
t_data = []
for dd in range(data.shape[0]):
  if data[dd]:
    v_data.append(data[dd])
    t_data.append(times[dd-1])

fig, axs = plt.subplots(1, 2, figsize=(15, 5))
axs[0].plot(times, true[:, 0])
axs[0].plot(t_data, v_data, 'ko', ms=3)
axs[0].set_xlabel("Time", fontsize=14)
axs[0].set_ylabel("Position", fontsize=14)
axs[1].plot(times, true[:, 1])
axs[1].set_xlabel("Time", fontsize=14)
axs[1].set_ylabel("Velocity", fontsize=14)
plt.show()

# Process noise
proc_var=0.1
proc_mat = np.zeros((2,2))
proc_mat[0, 0] = proc_var/3.0*dt**3
proc_mat[0, 1] = proc_var/2.0*dt**2
proc_mat[1, 0] = proc_var/2.0*dt**2
proc_mat[1, 1] = proc_var*dt
proc_mat_inv = np.linalg.pinv(proc_mat)
Lproc  = np.linalg.cholesky(proc_mat)

def proposal(proc_cov, meas_cov, current_state, data=None, dt=dt):
    """ Bootstrap Particle Filter the proposal is the dynamics!"""

    if current_state.ndim == 1:
        return pendulum_dyn(current_state, dt=dt) + np.dot(Lproc, np.random.randn(2))
    else:
        nsamples = current_state.shape[0]
        return pendulum_dyn(current_state, dt=dt) + np.dot(Lproc, np.random.randn(2, nsamples)).T

def proposal_logpdf(proc_cov, meas_cov,current, previous, data=None, proc_var=Q):
    """ Bootstrap Particle Filter: the proposal is the dynamics"""
    nexts  = pendulum_dyn(previous, dt=dt)
    delta = nexts - current
    if current.ndim == 1:
        return -0.5 * np.dot(delta, np.dot(proc_mat_inv, delta))
    else:
        return -0.5 * np.sum(delta * np.dot(delta, proc_mat_inv.T), axis=1)

def likelihood(proc_cov, meas_cov,state, data, noise_var=R):
    """Gaussian Likelihood through nonlinear model"""
    dpropose = observe(state)
    delta = dpropose - data
    if state.ndim == 1:
        return -0.5 * np.dot(delta, delta) / noise_var
    else:
        return -0.5 * np.sum(delta * delta, axis=1) / noise_var

# Dynamics as the proposal
R = 0.01 # 0.1, 0.01
samples, weights, eff =  particle_filter(Q, R, data, prior_mean, prior_cov,
                                            proposal, proposal_logpdf, likelihood, proposal_logpdf,
                                            nsamples=100000, resampling_threshold_frac=0.1)
ref_means, ref_stds = compute_mean_std(samples, weights)

#ExKF as the proposal
samples, weights, eff = particle_filter(Q, R, data, prior_mean, prior_cov,
                                        ekf_proposal, ekf_proposal_logpdf, likelihood, proposal_logpdf,
                                        nsamples=1000, resampling_threshold_frac=0.1)

plt.figure(figsize=(7,5))
plt.plot(eff, 'o')
plt.xlabel("Time", fontsize=14)
plt.ylabel("Effective Sample Size", fontsize=14)
plt.show()

means, stds = compute_mean_std(samples, weights)
fig, axs = plt.subplots(1, 2, figsize=(15, 5))

axs[0].plot(times, true[:, 0],'-r', label='True')
axs[0].plot(times, means[:, 0], '-', label='Filtered Mean')
axs[0].plot(times[1:], data[:, 0], 'ko', ms=1, label='Data')
axs[0].fill_between(times, means[:, 0] - 2 * stds[:, 0], means[:, 0]+2*stds[:, 0], color='blue', alpha=0.1, label=r'$2\sigma$')
axs[0].set_xlabel('Time',fontsize=14)
axs[0].set_ylabel('Position', fontsize=14)
axs[0].legend(fontsize=14)

axs[1].plot(times, true[:, 1],'-r', label='True')
axs[1].plot(times, means[:, 1], '-', label='Filtered Mean')
axs[1].fill_between(times, means[:, 1] - 2 * stds[:, 1], means[:, 1]+2*stds[:, 1], color='blue', alpha=0.1, label=r'$2\sigma$')
axs[1].set_xlabel('Time',fontsize=14)
axs[1].set_ylabel('Velocity', fontsize=14)

plt.show()

def plot_2d(weights, samples, xlim, ylim):
    """A function to plot an empirical distribution"""
    Nsamples = 3000
    s, w = resample(Nsamples, samples, weights) # resample to obtain equal weights

    xspace = np.linspace(xlim[0], xlim[1],100)
    yspace = np.linspace(ylim[0], ylim[1],100)
    XX, YY = np.meshgrid(xspace, yspace)

    fig, axs = plt.subplots(1,1)

    positions = np.vstack([XX.ravel(), YY.ravel()])
    values = np.vstack([s[:, 0], s[:, 1]])
    kernel = stats.gaussian_kde(values) # kernel density estimate to get contours
    f = np.reshape(kernel(positions).T, XX.shape)
    axs.contour(XX, YY, f,)
    axs.plot(s[:, 0], s[:, 1], 'x', color='grey', alpha=0.1)
    axs.set_xlabel("angle")
    axs.set_ylabel("angular rate")

    return fig, axs

xlim = [-3, 3]
ylim = [-6, 6]
N, d = means.shape
for ii in range(N):
    if ii % 20 == 0:
        print(ii, samples[ii].shape)
        fig, axs = plot_2d(weights[:, ii], samples[:, :, ii], xlim, ylim)
        axs.set_title("time = {:5E}".format(times[ii]))

def convergence_study(delta, R, reference_mean, reference_cov, num_particles_list):
    """
    Study convergence of mean and covariance with increasing particle counts.
    """
    mean_errors = []
    cov_errors = []

    for n in num_particles_list:
        samples, weights, eff = particle_filter(Q, R, data, prior_mean, prior_cov,
                                        ekf_proposal, ekf_proposal_logpdf, likelihood, proposal_logpdf,
                                        nsamples=n, resampling_threshold_frac=0.1)
        mean, cov = compute_mean_std(samples, weights)

        mean_error = np.linalg.norm(mean - reference_mean)
        cov_error = np.linalg.norm(cov - reference_cov)

        mean_errors.append(mean_error)
        cov_errors.append(cov_error)

    # Plot convergence
    plt.figure()
    plt.loglog(num_particles_list, mean_errors, label="Mean Error")
    plt.loglog(num_particles_list, cov_errors, label="Covariance Error")
    plt.xlabel("Number of Particles (N)")
    plt.ylabel("Error")
    plt.legend()
    plt.title("Convergence of Particle Filter with N")
    plt.show()

num_particles_list = [100, 1000, 5000, 10000]
convergence_study(delta, R, ref_means, ref_stds, num_particles_list)

