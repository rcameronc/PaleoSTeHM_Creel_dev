#----------------------Define Functions---------------------------
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import torch
import torch.distributions as torchdist
from torch.distributions import constraints
import pandas as pd
import pyro
import pyro.distributions as dist
from pyro.contrib.gp.models.model import GPModel
from pyro.contrib.gp.util import conditional
from pyro.nn.module import PyroParam, pyro_method,PyroSample
from pyro.util import warn_if_nan
from scipy import interpolate
from tqdm.notebook import tqdm
import torch
from torch.distributions import constraints
from pyro.contrib.gp.kernels.kernel import Kernel
from pyro.nn.module import PyroParam
from pyro.infer import MCMC, NUTS, HMC, Predictive

font = {'weight':'normal',
       'size':20}

matplotlib.rc('font',**font)

def load_rsl_data(file):
    '''
    A function to load rsl data from a csv file, this csv 
    file should be presented in the same format as NJ_CC.csv in data folder

    ---------Inputs---------
    file: str, the path to the csv file

    ---------Outputs---------
    X: torch.tensor, the age of rsl data
    y: torch.tensor, the rsl data
    y_sigma: torch.tensor, one sigma uncertainty of rsl data
    x_sigma: torch.tensor, one uncertainty of age data
    '''

    #load data
    data = pd.read_csv(file)
    rsl = data['RSL']
    rsl_2sd =( data['RSLer_up_2sd']+data['RSLer_low_2sd'])/2 #average up and low 2std
    rsl_age = -(data['Age']-1950) #convert age from BP to CE
    rsl_age_2sd = (data['Age_low_er_2sd']+data['Age_up_er_2sd'])/2 #average up and low 2std
    rsl_lon = data['Longitude']
    rsl_lat = data['Latitude']

    #convert RSL data into tonsors
    X = torch.tensor(rsl_age).flatten() #standardise age
    y = torch.tensor(rsl).flatten()
    y_sigma = torch.tensor(rsl_2sd/2).flatten()
    x_sigma = torch.tensor(rsl_age_2sd/2).flatten()

    return X,y,y_sigma,x_sigma,rsl_lon,rsl_lat

def plot_uncertainty_boxes(x, y, x_error, y_error,ax=None):
    '''
    A function to plot uncertainty box for data with vertical and horizontal uncertainties.

    -----------------Input-------------------
    x: a 1-D array of input data
    y: a 1-D array of ouput data
    x_error: a 1-D array containing 2 sigma uncertainty of input data
    y_error: a 1-D array containing 2 sigma uncertainty of output data

    ---------------Return-------------------
    ax: a matplotlib ax of output plot
    '''
    if ax==None: ax=plt.subplot(111)
    for i in range(len(x)):

        ax.add_patch(plt.Rectangle((x[i] - x_error[i], y[i] - y_error[i]), 2 * x_error[i], 2*  y_error[i], 
                                     fill=False, edgecolor='red', linewidth=3,alpha=0.5))
#     ax.set_xlim(np.min(x)-x_error[np.argmin(x)]*5,np.max(x)+x_error[np.argmax(x)]*5)
#     ax.set_ylim(np.min(y)-y_error[np.argmin(y)]*5,np.max(y)+y_error[np.argmax(y)]*5)
    ax.set_xlabel('Age (CE)')
    ax.set_ylabel('RSL (m)')

    return ax

def plot_tem_regreesion(data_age,data_rsl,data_age_sigma,data_rsl_sigma,mean_rsl_age,mean_rsl,
                        rsl_sd,rsl_rate_age,mean_rate,rate_sd,color='C0',axes=None,save=False):
    '''
    A function to create matplotlib plot for temporal regression results.

    -----------------Inputs-------------------
    data_age: a 1-D array of rsl age data
    data_rsl: a 1-D array of rsl data
    data_age_sigma: a 1-D array containing 1 sigma uncertainty of rsl age data
    data_rsl_sigma: a 1-D array containing 1 sigma uncertainty of rsl data
    mean_rsl_age: a 1-D array of testing age data, i.e., new_X for GP regression
    mean_rsl: a 1-D array of mean rsl regression results
    rsl_sd: a 1-D array of rsl regression standard deviation
    rsl_rate_age: a 1-D array of testing age data for rsl rate
    rsd_rate: a 1-D array of mean rsl rate regression results
    rate_sd: a 1-D array of rsl rate regression standard deviation
    axes: matplotlib axes, if None, create a new figure
    save: bool, whether to save the plot

    ---------------Output-------------------
    A matplotlib plot of temporal regression results which contains
    three sub-plots: 1) RSL data with uncertainty box and mean regression line; 2) RSL rate
    with uncertainty box and mean regression line; 3) Residual plot.


    '''
    #change torch tensor to numpy array for plotting
    if torch.is_tensor(data_age) ==True: data_age = data_age.detach().numpy()
    if torch.is_tensor(data_rsl) ==True: data_rsl = data_rsl.detach().numpy()
    if torch.is_tensor(data_age_sigma) ==True: data_age_sigma = data_age_sigma.detach().numpy()
    if torch.is_tensor(data_rsl_sigma) ==True: data_rsl_sigma = data_rsl_sigma.detach().numpy()
    if torch.is_tensor(mean_rsl_age) ==True: mean_rsl_age = mean_rsl_age.detach().numpy()
    if torch.is_tensor(mean_rsl) ==True: mean_rsl = mean_rsl.detach().numpy()
    if torch.is_tensor(rsl_sd) ==True: rsl_sd = rsl_sd.detach().numpy()
    if torch.is_tensor(rsl_rate_age) ==True: rsl_rate_age = rsl_rate_age.detach().numpy()
    if torch.is_tensor(mean_rate) ==True: mean_rate = mean_rate.detach().numpy()
    if torch.is_tensor(rate_sd) ==True: rate_sd = rate_sd.detach().numpy()

    if axes==None:
        fig,axes= plt.subplots(1,3,figsize=(36, 10))
    ax = axes[0]

    plot_uncertainty_boxes(data_age,data_rsl, data_age_sigma*2,data_rsl_sigma*2,ax=ax)

    ax.plot(mean_rsl_age,mean_rsl,linewidth=3)

    ax.fill_between(
            mean_rsl_age,  # plot the two-sigma uncertainty about the mean
            (mean_rsl - 2.0 * rsl_sd),
            (mean_rsl + 2.0 * rsl_sd),
            color=color,
            alpha=0.6,zorder=10)
    
    ax = axes[1]
    
    ax.plot(rsl_rate_age,mean_rate*1000,linewidth=3)
    ax.fill_between(
                rsl_rate_age,  # plot the two-sigma uncertainty about the mean
                (mean_rate - 2.0 * rate_sd)*1000,
                (mean_rate + 2.0 * rate_sd)*1000,
                color=color,
                alpha=0.6,zorder=10)
    ax.set_xlabel('Age (CE)')
    ax.set_ylabel('RSL rate (mm/year)')

    ax = axes[2]
    f = interpolate.interp1d(mean_rsl_age,mean_rsl)
    ax.scatter(data_age,(data_rsl-f(data_age))*1000,s=150,marker='*',color=color,alpha=0.6)
    ax.set_xlabel('Age (CE)')
    ax.set_ylabel('Residual (mm)');
    plt.show()

    if save: plt.savefig('../Figures/Temp_Regreesion.png',dpi=300)
    return axes

def plot_loss(loss):
    '''A function used to plot loss function variation'''
    plt.plot(loss)
    plt.xlabel("Iterations")
    _ = plt.ylabel("Loss")  # supress output text


class GPRegression_V(GPModel):
    r"""
    Gaussian Process Regression model.

    The core of a Gaussian Process is a covariance function :math:`k` which governs
    the similarity between input points. Given :math:`k`, we can establish a
    distribution over functions :math:`f` by a multivarite normal distribution

    .. math:: p(f(X)) = \mathcal{N}(0, k(X, X)),

    where :math:`X` is any set of input points and :math:`k(X, X)` is a covariance
    matrix whose entries are outputs :math:`k(x, z)` of :math:`k` over input pairs
    :math:`(x, z)`. This distribution is usually denoted by

    .. math:: f \sim \mathcal{GP}(0, k).

    .. note:: Generally, beside a covariance matrix :math:`k`, a Gaussian Process can
        also be specified by a mean function :math:`m` (which is a zero-value function
        by default). In that case, its distribution will be

        .. math:: p(f(X)) = \mathcal{N}(m(X), k(X, X)).

    Given inputs :math:`X` and their noisy observations :math:`y`, the Gaussian Process
    Regression model takes the form

    .. math::
        f &\sim \mathcal{GP}(0, k(X, X)),\\
        y & \sim f + \epsilon,

    where :math:`\epsilon` is Gaussian noise.

    .. note:: This model has :math:`\mathcal{O}(N^3)` complexity for training,
        :math:`\mathcal{O}(N^3)` complexity for testing. Here, :math:`N` is the number
        of train inputs.

    Reference:

    [1] `Gaussian Processes for Machine Learning`,
    Carl E. Rasmussen, Christopher K. I. Williams

    :param torch.Tensor X: A input data for training. Its first dimension is the number
        of data points.
    :param torch.Tensor y: An output data for training. Its last dimension is the
        number of data points.
    :param ~pyro.contrib.gp.kernels.kernel.Kernel kernel: A Pyro kernel object, which
        is the covariance function :math:`k`.
    :param torch.Tensor noise: Variance of Gaussian noise of this model.
    :param callable mean_function: An optional mean function :math:`m` of this Gaussian
        process. By default, we use zero mean.
    :param float jitter: A small positive term which is added into the diagonal part of
        a covariance matrix to help stablize its Cholesky decomposition.
    """

    def __init__(self, X, y, kernel, noise=None, mean_function=None, jitter=1e-6):
        assert isinstance(
            X, torch.Tensor
        ), "X needs to be a torch Tensor instead of a {}".format(type(X))
        if y is not None:
            assert isinstance(
                y, torch.Tensor
            ), "y needs to be a torch Tensor instead of a {}".format(type(y))
        super().__init__(X, y, kernel, mean_function, jitter)

#         noise = self.X.new_tensor(1.0) if noise is None else noise
        self.noise = noise
        self = self.double() #GP in pyro should use double precision
        self.X = self.X.double()
        self.y = self.y.double()
        self.noise = self.noise.double()
#         self.noise = PyroParam(noise, constraints.positive)
    @pyro_method
    def model(self):
        self.set_mode("model")

        N = self.X.size(0)
        Kff = self.kernel(self.X)
#         print(self.noise.abs() )

        Kff.view(-1)[:: N + 1] += self.jitter + self.noise  # add noise to diagonal
        Lff = torch.linalg.cholesky(Kff)

        zero_loc = self.X.new_zeros(self.X.size(0))
        f_loc = zero_loc + self.mean_function(self.X)
        if self.y is None:
            f_var = Lff.pow(2).sum(dim=-1)
            return f_loc, f_var
        else:
            return pyro.sample(
                self._pyro_get_fullname("y"),
                dist.MultivariateNormal(f_loc, scale_tril=Lff)
                .expand_by(self.y.shape[:-1])
                .to_event(self.y.dim() - 1),
                obs=self.y,
            )


    @pyro_method
    def guide(self):
        self.set_mode("guide")
        self._load_pyro_samples()


    def forward(self, Xnew, full_cov=False, noiseless=True):
        r"""
        Computes the mean and covariance matrix (or variance) of Gaussian Process
        posterior on a test input data :math:`X_{new}`:

        .. math:: p(f^* \mid X_{new}, X, y, k, \epsilon) = \mathcal{N}(loc, cov).

        .. note:: The noise parameter ``noise`` (:math:`\epsilon`) together with
            kernel's parameters have been learned from a training procedure (MCMC or
            SVI).

        :param torch.Tensor Xnew: A input data for testing. Note that
            ``Xnew.shape[1:]`` must be the same as ``self.X.shape[1:]``.
        :param bool full_cov: A flag to decide if we want to predict full covariance
            matrix or just variance.
        :param bool noiseless: A flag to decide if we want to include noise in the
            prediction output or not.
        :returns: loc and covariance matrix (or variance) of :math:`p(f^*(X_{new}))`
        :rtype: tuple(torch.Tensor, torch.Tensor)
        """
        self._check_Xnew_shape(Xnew)
        self.set_mode("guide")

        N = self.X.size(0)
        Kff = self.kernel(self.X).contiguous()
        Kff.view(-1)[:: N + 1] += self.jitter + self.noise  # add noise to the diagonal
        Lff = torch.linalg.cholesky(Kff)

        y_residual = self.y - self.mean_function(self.X)
        loc, cov = conditional(
            Xnew,
            self.X,
            self.kernel,
            y_residual,
            None,
            Lff,
            full_cov,
            jitter=self.jitter,
        )

        if full_cov and not noiseless:
            M = Xnew.size(0)
            cov = cov.contiguous()
            cov.view(-1, M * M)[:, :: M + 1] += self.noise  # add noise to the diagonal
        if not full_cov and not noiseless:
            cov = cov + self.noise.abs()

        return loc + self.mean_function(Xnew), cov


    def iter_sample(self, noiseless=True):
        r"""
        Iteratively constructs a sample from the Gaussian Process posterior.

        Recall that at test input points :math:`X_{new}`, the posterior is
        multivariate Gaussian distributed with mean and covariance matrix
        given by :func:`forward`.

        This method samples lazily from this multivariate Gaussian. The advantage
        of this approach is that later query points can depend upon earlier ones.
        Particularly useful when the querying is to be done by an optimisation
        routine.

        .. note:: The noise parameter ``noise`` (:math:`\epsilon`) together with
            kernel's parameters have been learned from a training procedure (MCMC or
            SVI).

        :param bool noiseless: A flag to decide if we want to add sampling noise
            to the samples beyond the noise inherent in the GP posterior.
        :returns: sampler
        :rtype: function
        """
        noise = self.noise.detach()
        X = self.X.clone().detach()
        y = self.y.clone().detach()
        N = X.size(0)
        Kff = self.kernel(X).contiguous()
        Kff.view(-1)[:: N + 1] += noise  # add noise to the diagonal

        outside_vars = {"X": X, "y": y, "N": N, "Kff": Kff}

        def sample_next(xnew, outside_vars):
            """Repeatedly samples from the Gaussian process posterior,
            conditioning on previously sampled values.
            """
            warn_if_nan(xnew)

            # Variables from outer scope
            X, y, Kff = outside_vars["X"], outside_vars["y"], outside_vars["Kff"]

            # Compute Cholesky decomposition of kernel matrix
            Lff = torch.linalg.cholesky(Kff)
            y_residual = y - self.mean_function(X)

            # Compute conditional mean and variance
            loc, cov = conditional(
                xnew, X, self.kernel, y_residual, None, Lff, False, jitter=self.jitter
            )
            if not noiseless:
                cov = cov + noise

            ynew = torchdist.Normal(
                loc + self.mean_function(xnew), cov.sqrt()
            ).rsample()

            # Update kernel matrix
            N = outside_vars["N"]
            Kffnew = Kff.new_empty(N + 1, N + 1)
            Kffnew[:N, :N] = Kff
            cross = self.kernel(X, xnew).squeeze()
            end = self.kernel(xnew, xnew).squeeze()
            Kffnew[N, :N] = cross
            Kffnew[:N, N] = cross
            # No noise, just jitter for numerical stability
            Kffnew[N, N] = end + self.jitter
            # Heuristic to avoid adding degenerate points
            if Kffnew.logdet() > -15.0:
                outside_vars["Kff"] = Kffnew
                outside_vars["N"] += 1
                outside_vars["X"] = torch.cat((X, xnew))
                outside_vars["y"] = torch.cat((y, ynew))

            return ynew

        return lambda xnew: sample_next(xnew, outside_vars)


def SVI_optm(gpr,num_iteration=1000,lr=0.05):
    '''
    A funciton to optimize the hyperparameters of a GP model using SVI

    ---------Inputs-----------
    gpr: a GP model defined by pyro GPR regression
    num_iteration: number of iterations for the optimization
    lr: learning rate for the optimization

    ---------Outputs-----------
    gpr: a GP model with optimized hyperparameters
    track: a dictionary of loss
    '''
    
    #clear the param store
    pyro.clear_param_store()
    #convert the model to double precision
    gpr = gpr.double()
    #define the optimiser
    optimizer = torch.optim.Adam(gpr.parameters(), lr=lr)
    #define the loss function
    loss_fn = pyro.infer.Trace_ELBO().differentiable_loss
    #do the optimisation
    track_list = []

    for i in tqdm(range(num_iteration)):
        optimizer.zero_grad()
        loss = loss_fn(gpr.model, gpr.guide)
        loss.backward()
        optimizer.step()
        gpr.set_mode("guide")
        track_list.append([loss.item(), *list(i2.item() for i2 in pyro.get_param_store().values())])
    
    #generate columns names for the track list
    col_name = ['loss' ]
    for i in (dict(pyro.get_param_store()).keys()):
        col_name.append(i[7:].replace('_map',''))
    #convert the track list to a dataframe
    track_list=pd.DataFrame(track_list,columns=col_name)

    return gpr,track_list


def SVI_NI_optm(gpr,x_sigma,num_iteration=1000,lr=0.05):
    '''
    A funciton to optimize the hyperparameters of a GP model using SVI

    ---------Inputs-----------
    gpr: a GP model defined by pyro GPR regression
    x_sigma: one sigma uncertainty for input data
    num_iteration: number of iterations for the optimization
    lr: learning rate for the optimization

    ---------Outputs-----------
    gpr: a GP model with optimized hyperparameters
    track: a dictionary of loss
    '''
    
    #clear the param store
    pyro.clear_param_store()
    #convert the model to double precision
    gpr = gpr.double()
    #define the optimiser
    optimizer = torch.optim.Adam(gpr.parameters(), lr=lr)
    #define the loss function
    loss_fn = pyro.infer.Trace_ELBO().differentiable_loss
    #do the optimisation
    track_list = []
    y_sigma = gpr.noise.detach().numpy()**0.5
    for i in tqdm(range(num_iteration)):
        #update the variance for every 100 iterations
        if i>0 and i%100==0:
            x_test = torch.tensor(gpr.X.clone().float(),requires_grad=True)
            y_mean, y_var = gpr(x_test.double(), full_cov=False)
            y_mean.sum().backward(retain_graph=True)
            y_rate = x_test.grad.detach().numpy()
            new_sigma = np.sqrt((y_rate**2*(x_sigma.detach().numpy())**2)+y_sigma**2)
            gpr.noise = torch.tensor(new_sigma**2)
        optimizer.zero_grad()
        loss = loss_fn(gpr.model, gpr.guide)
        loss.backward()
        optimizer.step()
        gpr.set_mode("guide")
        track_list.append([loss.item(), *list(i2.item() for i2 in pyro.get_param_store().values())])
    
    #generate columns names for the track list
    col_name = ['loss' ]
    for i in (dict(pyro.get_param_store()).keys()):
        col_name.append(i[7:].replace('_map',''))
    #convert the track list to a dataframe
    track_list=pd.DataFrame(track_list,columns=col_name)

    return gpr,track_list

def plot_track_list(track_list):
    '''
    A function to plot the track_list generated from SVI_optm function
    '''
    
    if track_list.shape[1]%3==0:
        row_num = (track_list.shape[1])//3
    else:
        row_num = track_list.shape[1]//3+1

    fig,axes = plt.subplots(row_num,3,figsize=(30,row_num*8))

    if row_num==1:
        for i in range(row_num*3):
            axes[i].plot(np.arange(len(track_list)),track_list.iloc[:,i])
            axes[i].set_title('{} : {:6.6f}'.format(track_list.columns[i]
                                                    ,track_list.iloc[-1,i]))
    
    else:
        for i in range(row_num):
            for j in range(3):
                if i*3+j < track_list.shape[1]:
                    axes[i,j].plot(np.arange(len(track_list)),track_list.iloc[:,i*3+j])
                    axes[i,j].set_title('{}: {:6.6f}'.format(track_list.columns[i*3+j],
                                                            track_list.iloc[-1,i*3+j]))
                else:
                    axes[i,j].set_visible(False)

    return axes

def NUTS_mcmc(gpr,num_samples=1500,warmup_steps=200,target_accept_prob = 0.8,print_stats=False):
    '''
    A function to run NUTS MCMC for GP regression model

    ----------Inputs---------
    gpr: a pyro GP regression model
    num_samples: number of samples to draw from the posterior
    warmup_steps: number of warmup steps for NUTS
    target_accept_prob: target acceptance probability for NUTS
    print_stats: whether to print the states of the model

    ----------Outputs---------
    mcmc: a pyro MCMC object
    
    '''
    hmc_kernel = NUTS(gpr.model,target_accept_prob=target_accept_prob)
    mcmc = MCMC(hmc_kernel, num_samples=num_samples,warmup_steps=warmup_steps)
    mcmc.run()
    if print_stats:
        for name, value in mcmc.get_samples().items():
            if 'kernel' in name:
                
                print('-----{}: {:4.2f} +/ {:4.2f} (2sd)-----'.format(name,value.mean(),2*value.std()))
                print('Gelman-Rubin statistic for {}: {:4.2f}'.format(name,mcmc.diagnostics()[name]['r_hat'].item()))
                print('Effective sample size for {}: {:4.2f}'.format(name,mcmc.diagnostics()[name]['n_eff'].item()))

    return mcmc

def mcmc_predict(input_gpr,mcmc,Xnew,thin_index=1):
    '''
    A function to prediction posterior mean and covariance of GP regression model

    ----------Inputs----------
    input_gpr: a pyro GP regression model
    mcmc: a pyro MCMC object
    Xnew: a torch tensor of new input data

    ----------Outputs----------
    full_bayes_mean_mean: a numpy array of posterior mean of GP regression model
    full_bayes_cov_mean: a numpy array of posterior covariance of GP regression model
    full_bayes_std_mean: a numpy array of posterior standard deviation of GP regression model
    '''
    
    def predictive(X_new,gpr):
        y_loc, y_cov = gpr(X_new,full_cov=True)
        pyro.sample("y", dist.Delta(y_loc))
        pyro.sample("y_cov", dist.Delta(y_cov))
        
    Xnew = torch.tensor(Xnew).double()
    thin_mcmc = mcmc.get_samples()
    for i in thin_mcmc:
        thin_mcmc[i] = thin_mcmc[i][::thin_index]

    posterior_predictive = Predictive(predictive, thin_mcmc)
    full_bayes_mean,full_bayes_cov = posterior_predictive.get_samples(Xnew,input_gpr).values()
    full_bayes_mean_mean = full_bayes_mean.mean(axis=0).detach().numpy()
    full_bayes_cov_mean = full_bayes_cov.mean(axis=0).detach().numpy()
    full_bayes_std_mean = np.diag(full_bayes_cov_mean)**0.5
    likelihood_list = []
    noise = np.ones(len(input_gpr.X))*input_gpr.noise.detach().numpy()

    for i in range(len(full_bayes_mean)):
        f = interpolate.interp1d(Xnew,full_bayes_mean[i])
        likelihood_list.append(cal_likelihood(input_gpr.y.detach().numpy(),
                                              noise**0.5,
                                              f(input_gpr.X)))
        
    return full_bayes_mean_mean,full_bayes_cov_mean,full_bayes_std_mean,likelihood_list

def cal_rate_var(test_X,cov_matrix,mean_rsl,difftimestep=200):
    '''A function to caluclate standard deviation of sea-levle change rate (i.e., first derivative of 
    GP).
    ------------------Inputs----------------------------
    test_X: an array of test input values
    cov_matrix: full covariance matrix from GP regression
    mean_rsl: GP regression produced mean RSL prediction
    difftimestep: time period for averaging 
    
    ------------------Outputs---------------------------
    difftimes: time series for the outputs
    rate: averaged sea-level change rate
    rate_sd: averaged sea-level change rate standard deviation
    '''
    
    Mdiff = np.array(np.equal.outer(test_X, test_X.T),dtype=int) - np.array(np.equal.outer(test_X, test_X.T + difftimestep),dtype=int)
    Mdiff = Mdiff * np.equal.outer(np.ones(len(test_X))*1, np.ones(len(test_X)))
    sub = np.where(np.sum(Mdiff, axis=1) == 0)[0]
    Mdiff = Mdiff[sub, :]
    difftimes = np.abs(Mdiff) @ test_X / np.sum(np.abs(Mdiff), axis=1)
    Mdiff = Mdiff / (Mdiff @ test_X.T)[:,None]
    rate_sd = np.sqrt(np.diag(Mdiff @ cov_matrix @ Mdiff.T))
    rate = Mdiff @ mean_rsl
    
    return difftimes,rate, rate_sd

def cal_misfit(y,y_sigma,prediction):
    
    return np.mean(np.sqrt(((y-prediction)/y_sigma)**2))

def cal_likelihood(y,y_std,pred):
    '''A function used to calcualte log likelihood function for a given prediction.
    This calculation only considers uncertainty in y axis. 
    
    ------------Inputs------------------
    y: reconstructed rsl
    y_std: standard deviation of reconstructed rsl
    pred: mean predction of rsl
    
    ------------Outputs------------------
    likelihood: mean likelihood of prediction fit to observation
    '''
    from scipy.stats import norm

    log_likelihood = 1 
    for i in range(len(y)):
        
        norm_dis = norm(y[i], y_std[i])
        log_likelihood+=np.log(norm_dis.pdf(pred[i]))
    
    return log_likelihood

class GPRegression_EIV(GPModel):
    r"""
    Gaussian Process Regression model.

    The core of a Gaussian Process is a covariance function :math:`k` which governs
    the similarity between input points. Given :math:`k`, we can establish a
    distribution over functions :math:`f` by a multivarite normal distribution

    .. math:: p(f(X)) = \mathcal{N}(0, k(X, X)),

    where :math:`X` is any set of input points and :math:`k(X, X)` is a covariance
    matrix whose entries are outputs :math:`k(x, z)` of :math:`k` over input pairs
    :math:`(x, z)`. This distribution is usually denoted by

    .. math:: f \sim \mathcal{GP}(0, k).

    .. note:: Generally, beside a covariance matrix :math:`k`, a Gaussian Process can
        also be specified by a mean function :math:`m` (which is a zero-value function
        by default). In that case, its distribution will be

        .. math:: p(f(X)) = \mathcal{N}(m(X), k(X, X)).

    Given inputs :math:`X` and their noisy observations :math:`y`, the Gaussian Process
    Regression model takes the form

    .. math::
        f &\sim \mathcal{GP}(0, k(X, X)),\\
        y & \sim f + \epsilon,

    where :math:`\epsilon` is Gaussian noise.

    .. note:: This model has :math:`\mathcal{O}(N^3)` complexity for training,
        :math:`\mathcal{O}(N^3)` complexity for testing. Here, :math:`N` is the number
        of train inputs.

    Reference:

    [1] `Gaussian Processes for Machine Learning`,
    Carl E. Rasmussen, Christopher K. I. Williams

    :param torch.Tensor X: A input data for training. Its first dimension is the number
        of data points.
    :param torch.Tensor y: An output data for training. Its last dimension is the
        number of data points.
    :param ~pyro.contrib.gp.kernels.kernel.Kernel kernel: A Pyro kernel object, which
        is the covariance function :math:`k`.
    :param torch.Tensor noise: Variance of Gaussian noise of this model.
    :param callable mean_function: An optional mean function :math:`m` of this Gaussian
        process. By default, we use zero mean.
    :param float jitter: A small positive term which is added into the diagonal part of
        a covariance matrix to help stablize its Cholesky decomposition.
    """

    def __init__(self, X, y, xerr,kernel, noise=None, mean_function=None, jitter=1e-6):
        assert isinstance(
            X, torch.Tensor
        ), "X needs to be a torch Tensor instead of a {}".format(type(X))
        if y is not None:
            assert isinstance(
                y, torch.Tensor
            ), "y needs to be a torch Tensor instead of a {}".format(type(y))
        
        super().__init__(X, y,kernel, mean_function, jitter)

        self.noise = noise
        self.xerr = xerr
    @pyro_method
    def model(self):
        self.set_mode("model")
        N = self.X.size(0)
        x_noise = pyro.sample('obs',dist.Normal(torch.zeros(N),self.xerr**0.5).to_event(1))
        X_noisy = (self.X+x_noise)
        Kff = self.kernel(X_noisy)
        Kff.view(-1)[:: N + 1] += self.jitter + self.noise  # add noise to diagonal
        Lff = torch.linalg.cholesky(Kff)
        zero_loc = X_noisy.new_zeros(X_noisy.size(0))
        f_loc = zero_loc + self.mean_function(X_noisy)
        if self.y is None:
            f_var = Lff.pow(2).sum(dim=-1)
            return f_loc, f_var
        else:

            return pyro.sample(
                self._pyro_get_fullname("y"),
                dist.MultivariateNormal(f_loc, scale_tril=Lff)
                .expand_by(self.y.shape[:-1])
                .to_event(self.y.dim() - 1),
                obs=self.y,
            )


    @pyro_method
    def guide(self):
        self.set_mode("guide")
        self._load_pyro_samples()

    def forward(self, Xnew, full_cov=False, noiseless=True):
        r"""
        Computes the mean and covariance matrix (or variance) of Gaussian Process
        posterior on a test input data :math:`X_{new}`:

        .. math:: p(f^* \mid X_{new}, X, y, k, \epsilon) = \mathcal{N}(loc, cov).

        .. note:: The noise parameter ``noise`` (:math:`\epsilon`) together with
            kernel's parameters have been learned from a training procedure (MCMC or
            SVI).

        :param torch.Tensor Xnew: A input data for testing. Note that
            ``Xnew.shape[1:]`` must be the same as ``self.X.shape[1:]``.
        :param bool full_cov: A flag to decide if we want to predict full covariance
            matrix or just variance.
        :param bool noiseless: A flag to decide if we want to include noise in the
            prediction output or not.
        :returns: loc and covariance matrix (or variance) of :math:`p(f^*(X_{new}))`
        :rtype: tuple(torch.Tensor, torch.Tensor)
        """
        self._check_Xnew_shape(Xnew)
        self.set_mode("guide")

        N = self.X.size(0)
        Kff = self.kernel(self.X).contiguous()
        Kff.view(-1)[:: N + 1] += self.jitter + self.noise  # add noise to the diagonal
        Lff = torch.linalg.cholesky(Kff)

        y_residual = self.y - self.mean_function(self.X)
        loc, cov = conditional(
            Xnew,
            self.X,
            self.kernel,
            y_residual,
            None,
            Lff,
            full_cov,
            jitter=self.jitter,
        )

        if full_cov and not noiseless:
            M = Xnew.size(0)
            cov = cov.contiguous()
            cov.view(-1, M * M)[:, :: M + 1] += self.noise  # add noise to the diagonal
        if not full_cov and not noiseless:
            cov = cov + self.noise.abs()

        return loc + self.mean_function(Xnew), cov

#-------------------------Define Spatio-temporal GP kernels-------------------------

def _torch_sqrt(x, eps=1e-12):
    """
    A convenient function to avoid the NaN gradient issue of :func:`torch.sqrt`
    at 0.
    """
    # Ref: https://github.com/pytorch/pytorch/issues/2421
    return (x + eps).sqrt()


class Isotropy(Kernel):
    """
    Base class for a family of isotropic covariance kernels which are functions of the
    distance :math:`|x-z|/l`, where :math:`l` is the length-scale parameter.

    By default, the parameter ``lengthscale`` has size 1. To use the isotropic version
    (different lengthscale for each dimension), make sure that ``lengthscale`` has size
    equal to ``input_dim``.

    :param torch.Tensor lengthscale: Length-scale parameter of this kernel.
    """

    def __init__(self, input_dim, variance=None, lengthscale=None, s_lengthscale=None,active_dims=None,geo=False):
        super().__init__(input_dim, active_dims)

        variance = torch.tensor(1.0) if variance is None else variance
        self.variance = PyroParam(variance, constraints.positive)
        if geo==False:
            lengthscale = torch.tensor(1.0) if lengthscale is None else lengthscale
            self.lengthscale = PyroParam(lengthscale, constraints.positive)
        else:
            s_lengthscale = torch.tensor(1.0) if s_lengthscale is None else s_lengthscale
            self.s_lengthscale = PyroParam(s_lengthscale, constraints.positive)

        self.geo= geo
        
    def _square_scaled_dist(self, X, Z=None):
        """
        Returns :math:`\|\frac{X-Z}{l}\|^2`.
        """
        if Z is None:
            Z = X
        X = self._slice_input(X)
        Z = self._slice_input(Z)
        if X.size(1) != Z.size(1):
            raise ValueError("Inputs must have the same number of features.")

        scaled_X = X / self.lengthscale
        scaled_Z = Z / self.lengthscale
        X2 = (scaled_X**2).sum(1, keepdim=True)
        Z2 = (scaled_Z**2).sum(1, keepdim=True)
        XZ = scaled_X.matmul(scaled_Z.t())
        r2 = X2 - 2 * XZ + Z2.t()
        return r2.clamp(min=0)

    def _scaled_dist(self, X, Z=None):
        """
        Returns :math:`\|\frac{X-Z}{l}\|`.
        """
        return _torch_sqrt(self._square_scaled_dist(X, Z))

    def _diag(self, X):
        """
        Calculates the diagonal part of covariance matrix on active features.
        """
        return self.variance.expand(X.size(0))

    def _scaled_geo_dist2(self,X,Z=None):
        '''
        A function to calculate the squared distance matrix between each pair of X.
        The function takes a PyTorch tensor of X and returns a matrix
        where matrix[i, j] represents the spatial distance between the i-th and j-th X.
        
        -------Inputs-------
        X: PyTorch tensor of shape (n, 2), representing n pairs of (lat, lon) X
        R: approximate radius of earth in km
        
        -------Outputs-------
        distance_matrix: PyTorch tensor of shape (n, n), representing the distance matrix
        '''
        if Z is None:
            Z = X

        # Convert coordinates to radians
        X = torch.tensor(X)
        Z = torch.tensor(Z)
        X_coordinates_rad = torch.deg2rad(X)
        Z_coordinates_rad = torch.deg2rad(Z)
        
        # Extract latitude and longitude tensors
        X_latitudes_rad = X_coordinates_rad[:, 0]
        X_longitudes_rad = X_coordinates_rad[:, 1]

        Z_latitudes_rad = Z_coordinates_rad[:, 0]
        Z_longitudes_rad = Z_coordinates_rad[:, 1]

         # Calculate differences in latitude and longitude
        dlat = X_latitudes_rad[:, None] - Z_latitudes_rad[None, :]
        dlon = X_longitudes_rad[:, None] - Z_longitudes_rad[None, :]
        # Apply Haversine formula
        a = torch.sin(dlat / 2) ** 2 + torch.cos(X_latitudes_rad[:, None]) * torch.cos(Z_latitudes_rad[None, :]) * torch.sin(dlon / 2) ** 2
        c = 2 * torch.atan2(torch.sqrt(a), torch.sqrt(1 - a))

        # Calculate the distance matrix
        distance_matrix = c / self.s_lengthscale

        return distance_matrix**2
    
    def _scaled_geo_dist(self, X, Z=None):
        """
        Returns :geo distance between X
        """
        return _torch_sqrt(self._scaled_geo_dist2(X, Z))

class RBF(Isotropy):
    r"""
    Implementation of Radial Basis Function kernel:

        :math:`k(x,z) = \sigma^2\exp\left(-0.5 \times \frac{|x-z|^2}{l^2}\right).`

    .. note:: This kernel also has name `Squared Exponential` in literature.
    """

    def __init__(self, input_dim, variance=None, lengthscale=None, s_lengthscale=None,active_dims=None,geo=False):
        super().__init__(input_dim,variance, lengthscale,s_lengthscale, active_dims,geo)

    def forward(self, X, Z=None, diag=False):
        
        if diag:
            return self._diag(X)
        if Z is None: Z=X

        if self.geo==False:
            r2 = self._square_scaled_dist(X[:,:1], Z[:,:1])
            return self.variance * torch.exp(-0.5 * r2)
        else:
            r2 = self._scaled_geo_dist2(X[:,1:],Z[:,1:])
            return torch.exp(-0.5 * r2)
        



class RationalQuadratic(Isotropy):
    r"""
    Implementation of RationalQuadratic kernel:

        :math:`k(x, z) = \sigma^2 \left(1 + 0.5 \times \frac{|x-z|^2}{\alpha l^2}
        \right)^{-\alpha}.`

    :param torch.Tensor scale_mixture: Scale mixture (:math:`\alpha`) parameter of this
        kernel. Should have size 1.
    """

    def __init__(
        self,
        input_dim,
        variance=None,
        lengthscale=None,
        s_lengthscale=None,
        scale_mixture=None,
        active_dims=None,
        geo=False
    ):
        super().__init__(input_dim, variance, lengthscale,s_lengthscale, active_dims,geo)

        if scale_mixture is None:
            scale_mixture = torch.tensor(1.0)
        self.scale_mixture = PyroParam(scale_mixture, constraints.positive)

    def forward(self, X, Z=None, diag=False):
        if diag:
            return self._diag(X)
        
        if Z is None: Z=X

        if self.geo==False:
            r2 = self._square_scaled_dist(X[:,:1], Z[:,:1])
            return self.variance * (1 + (0.5 / self.scale_mixture) * r2).pow(
            -self.scale_mixture
        )
        else:
            r2 = self._scaled_geo_dist2(X[:,1:],Z[:,1:])
            return (1 + (0.5 / self.scale_mixture) * r2).pow(
            -self.scale_mixture
            )           
        



class Exponential(Isotropy):
    r"""
    Implementation of Exponential kernel:

        :math:`k(x, z) = \sigma^2\exp\left(-\frac{|x-z|}{l}\right).`
    """

    def __init__(self, input_dim, variance=None, lengthscale=None, s_lengthscale=None,active_dims=None,geo=False):
        super().__init__(input_dim, variance, lengthscale, s_lengthscale, active_dims,geo)

    def forward(self, X, Z=None, diag=False):
        if diag:
            return self._diag(X)
        
        if Z is None: Z=X

        if self.geo==False:
            r = self._scaled_dist(X[:,:1], Z[:,:1])
            return self.variance * torch.exp(-r)
        else:
            r = self._scaled_geo_dist(X[:,1:],Z[:,1:])
            return torch.exp(-r)
        



class Matern32(Isotropy):
    r"""
    Implementation of Matern32 kernel:

        :math:`k(x, z) = \sigma^2\left(1 + \sqrt{3} \times \frac{|x-z|}{l}\right)
        \exp\left(-\sqrt{3} \times \frac{|x-z|}{l}\right).`
    """

    def __init__(self, input_dim, variance=None, lengthscale=None, s_lengthscale=None, active_dims=None,geo=False):
        super().__init__(input_dim, variance, lengthscale, s_lengthscale, active_dims,geo)

    def forward(self, X, Z=None, diag=False):
        if diag:
            return self._diag(X)
        
        if Z is None: Z=X

        if self.geo==False:
            r = self._scaled_dist(X[:,:1], Z[:,:1])
            sqrt3_r = 3**0.5 * r
            return self.variance * (1 + sqrt3_r) * torch.exp(-sqrt3_r)
        else:
            r = self._scaled_geo_dist(X[:,1:],Z[:,1:])
            sqrt3_r = 3**0.5 * r
            return (1 + sqrt3_r) * torch.exp(-sqrt3_r)
        



class Matern52(Isotropy):
    r"""
    Implementation of Matern52 kernel:

        :math:`k(x,z)=\sigma^2\left(1+\sqrt{5}\times\frac{|x-z|}{l}+\frac{5}{3}\times
        \frac{|x-z|^2}{l^2}\right)\exp\left(-\sqrt{5} \times \frac{|x-z|}{l}\right).`
    """

    def __init__(self, input_dim, variance=None, lengthscale=None, s_lengthscale=None, active_dims=None,geo=False):
        super().__init__(input_dim, variance, lengthscale, s_lengthscale, active_dims,geo)

    def forward(self, X, Z=None, diag=False):
        if diag:
            return self._diag(X)
        
        if Z is None: Z=X

        if self.geo==False:
            r2 = self._square_scaled_dist(X[:,:1], Z[:,:1])
            r = _torch_sqrt(r2)
            sqrt5_r = 5**0.5 * r
            return self.variance * (1 + sqrt5_r + (5 / 3) * r2) * torch.exp(-sqrt5_r)
        else:
            r2 = self._scaled_geo_dist2(X[:,1:],Z[:,1:])
            r = _torch_sqrt(r2)
            sqrt5_r = 5**0.5 * r
            return (1 + sqrt5_r + (5 / 3) * r2) * torch.exp(-sqrt5_r)
        
        