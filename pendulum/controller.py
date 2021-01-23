import numpy as np
from scipy import spatial
import cvxpy as cp
from collections import deque
from scipy.signal import cont2discrete
from scipy import optimize
import matplotlib.pyplot as plt
from sklearn.gaussian_process import GaussianProcessRegressor
import sklearn.gaussian_process
import time


class Controller(object):
    '''
    Class template for pendulum controller
    '''
    def __init__(self, init_state):
        self.init_state = init_state
    
    def policy(self, state):
        '''
        A controller must have a policy action.
        
        Parameters
        ----------
        state: (float, float, float float)
            The current system state
        
        Returns
        -------
        float
            The controller action, in force applied to the cart.
        '''
        raise NotImplementedError

 

class MPCController(Controller):
    def __init__(self, pendulum, T, dt, u_max=1000, plotting=False):
        self.pendulum = pendulum 
        self.plotting = plotting
        self.setpoint = 0
        
        # System A 
        # nxn

        A = np.array([
            [0, 1, 0, 0],
            [0, 0, (pendulum.g * pendulum.m)/pendulum.M, 0],
            [0, 0, 0, 1],
            [0, 0, pendulum.g/pendulum.l + pendulum.g * pendulum.m/(pendulum.l*pendulum.M), 0]
        ])

        # Input B
        # n x p

        B = np.array([
            [0], 
            [1/pendulum.M],
            [0],
            [1/pendulum.M*pendulum.l]
            
        ])

        # Output C
        # q x n
        # 
        # (blank for now)

        C = np.zeros((1, A.shape[0]))

        # Feedthrough D
        # q x p
        # 
        # (blank for now)
        
        D = np.zeros((1, 1))

        sys_disc = cont2discrete((A,B,C,D), dt, method='zoh')
        self.A = sys_disc[0]
        self.B = sys_disc[1]
        
        self.T = T
        self.u_max = u_max

        self.planned_u = []
        self.planned_state = []

    def policy(self, state, t, dt):
        x = cp.Variable((4, self.T+1))
        u = cp.Variable((1, self.T))
        cost = 0
        constr = []
        for t in range(self.T):
            constr.append(x[:, t + 1] == self.A @ x[:, t] + self.B @ u[:, t])
            constr.append(cp.abs(u[:, t]) <= self.u_max)
        cost += cp.sum_squares(x[2,self.T])
        cost += 1e4*cp.sum_squares(u[0,self.T-1])
        constr += [x[:, 0] == state]
        problem = cp.Problem(cp.Minimize(cost), constraints=constr)
        problem.solve(verbose=False, solver='ECOS')
        action = u[0,0].value

        # dump estimate info
        self.planned_state = x[:,:].value
        self.planned_u = u[0,:].value

        # print('x: {}'.format(x[:,:].value))
        return action       

    def init_plot(self):
        prediction = plt.figure()
        return prediction

    def update_plot(self, figure):
        plt.clf()
        ax0 = figure.add_subplot(211)
        ax1 = figure.add_subplot(212)
        # States
        ax0.plot(self.planned_state[0], label=r'$x$')
        ax0.plot(self.planned_state[1], label=r'$\dot{x}$') 
        ax0.plot(self.planned_state[2], label=r'$\theta$')
        ax0.plot(self.planned_state[3], label=r'$\dot{\theta}$')   
        ax0.axhline(y = self.setpoint, color='k', drawstyle='steps', linestyle='dotted', label=r'set point')
        ax0.set_ylabel("state")
        ax0.legend()
        # Control Actions
        ax1.plot(self.planned_u, label=r'$u$')
        ax1.set_ylabel("force")
        ax1.legend()
        plt.draw()
        plt.pause(0.0001)


class NoController(Controller):
    def __init__(self):
        pass
    
    def policy(self, state, t, dt):
        return 0

class MPCWithGPR(Controller):
    def __init__(self, pend, dt, window=8, every=5, future=10, plotting=False):
        # prior observations
        self.M = window
        self.T = future
        self.pend = pend
        self.plotting = plotting
        self.l_pred_x_k = np.zeros((1,4))
        self.l_err_x_k = np.zeros((1,4))
        self.nl_pred_x_k = np.zeros((1,4))
        self.nl_err_x_k = np.zeros((1,4))
        self.pred_mu = np.zeros((1,4))
        self.pred_sig = np.zeros((1,4))
        self.l_pred_state = np.zeros((1,4))
        self.nl_pred_state = np.zeros((1,4))
        self.have_pred = False
        self.prior_action = 0
        self.z_current = np.zeros((1, 5))
        self.z_points = np.zeros((self.M,5))
        self.y_points = np.zeros((self.M,4))

        # prior points
        self.priors = deque()
        self.x_k1 = np.empty(5)
        self.K = np.zeros((np.size(self.M),np.size(self.M)))
    
        A = np.array([
            [0, 1, 0, 0],
            [0, 0, (pend.g * pend.m)/pend.M, 0],
            [0, 0, 0, 1],
            [0, 0, pend.g/pend.l + pend.g * pend.m/(pend.l*pend.m), 0]])
        B = np.array([
            [0], 
            [1/pend.M], 
            [0], 
            [1/(pend.M * pend.l)]])
        C = np.zeros((1, A.shape[0]))
        D = np.zeros((1, 1))
        sys_disc = cont2discrete((A,B,C,D), dt * every, method='zoh')
        self.A = sys_disc[0]
        self.B = sys_disc[1]
        self.t_priors = []
        self.x_priors = []
        self.u_priors = []
        self.tick = 0

    def apply_kernel(self, x1, x2=None, l=1, sigma=1):
        if x2 is None:
            diff = spatial.distance.pdist(x1, metric='sqeuclidean')
            gram = np.exp(diff/l * -0.5)
            gram = spatial.distance.squareform(gram)
            np.fill_diagonal(gram, 1)
        else:
            diff = spatial.distance.cdist(x1, x2, metric='sqeuclidean')
            gram = np.exp(diff/l * - 0.5)
        return gram

    def ll_loss(self, z, y, theta):
        K = self.apply_kernel(z, a=theta)
        K[np.diag_indices_from(K)] += np.var(y, axis=1) + 1e-8
        L = np.linalg.cholesky(K)
        alpha = np.linalg.solve(L.T, np.linalg.solve(L, y))
        a = -0.5 * np.dot(y.T, alpha)
        b = -0.5 * np.log(np.trace(L))
        c = -0.5 * L.shape[0] * np.log(np.pi * 2)
        ll = a + b + c
        return ll.sum()
    
    def optimize(self, z, y):
        theta = 1
        def obj_func(theta, z, y):
            return -self.ll_loss(z, y, theta)

        results = optimize.minimize(
            obj_func,
            theta,
            (z, y),
            method='L-BFGS-B',
            options={'disp': True}
        )
        print('\ttheta={}'.format(results['x']))
        return(results['x'])

    def make_prediction(self, z, y, x, u):
        '''
        z: prior   x, u
        y: prior g(x, u)

        x: state
        u: control input
        '''
        # prefill
        mu = np.zeros((1,np.shape(y)[1]))
        sigma = np.zeros((1,np.shape(y)[1]))
        z_new = np.empty((1,5))
        z_new[:, :4] = np.asarray(x)
        z_new[:, 4] = np.asarray(u)

        l = 1
        s = 10
        K = self.apply_kernel(z, l=l, sigma=s)
        K[np.diag_indices_from(K)] += np.var(y, axis=1) + 1e-9
        L = np.linalg.cholesky(K)

        for a in range(y.shape[1]):
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, y[:,a]))
            # mean
            z_star = self.apply_kernel(z_new, z, l=l, sigma=s)
            mu[0,a] = z_star.dot(alpha)
            # variance
            v = np.linalg.solve(L, z_star.T)
            sigma[0,a] = self.apply_kernel(z_new, z_new, l=l, sigma=s) - np.dot(v.T, v)
        # sigma = np.sqrt(sigma)
        return mu, sigma

    def policy(self, state, t, dt):
        if self.tick > self.M +1:
            self.priors.popleft()

            # record predictions
            if self.have_pred == True:
                self.l_pred_x_k = np.atleast_2d(self.l_pred_state)
                self.l_err_x_k = np.atleast_2d(state - self.l_pred_state)
                self.nl_pred_x_k = np.atleast_2d(self.nl_pred_state)
                self.nl_err_x_k = np.atleast_2d(state - self.nl_pred_state)

            # first val = most recent
            xk1 = np.atleast_2d(self.priors)[:-1,:]
            xk  = np.atleast_2d(self.priors)[1:,:]
            linear_xk = np.dot(xk1[:,:4], self.A) + np.dot(np.atleast_2d(xk1[:,4]).T, self.B.T)
            y = linear_xk - xk[:,:4] # M x n_d
            z = xk1 # M x n_z

            self.pred_mu, self.pred_sig = self.make_prediction(z, y, state, self.prior_action)
            
            # write predictions
            self.l_pred_state = np.dot(np.atleast_2d(state), self.A)
            self.nl_pred_state = self.l_pred_state - self.pred_mu
            self.have_pred = True

            self.z_current = np.atleast_2d(state)
            self.z_points = z[:,:4]
            self.y_points = y
        
        else:
            pass # action=0
        action = 0
        self.prior_action = action
        to_append = list(state) + [action]
        self.priors.append(to_append)
        self.tick += 1
        return action
 

    def init_plot(self):
        f = plt.figure(figsize=(8,8))
        return f

    def update_plot(self, fig):
        # only for those items in the state space...
        # e.g. 4 vars in state space, so we set rows=2 and cols=2.
        ss_labels = [r'$x$', r'$\dot{x}$', r'$\theta$', r'$\dot{\theta}$']
        # Clear the figure before redraw
        plt.clf()

        ax1 = fig.add_subplot(3,2,1)
        ax1.scatter(self.z_points[:, 0], self.y_points[:, 0], c='k', marker='.', label='training set')
        ax1.scatter(self.z_current[:,0], self.pred_mu[:,0], c='r', marker='.', label='prediction')
        ax1.set_xlabel('k ' + ss_labels[0])
        ax1.set_ylabel('k+1 error in ' + ss_labels[0])
        ax1.set_title('predicting k+1 error ' + ss_labels[0])
        
        ax2 = fig.add_subplot(3,2,2)
        ax2.scatter(self.z_points[:, 1], self.y_points[:, 1], c='k', marker='.', label='training set')
        ax2.scatter(self.z_current[:,1], self.pred_mu[:,1], c='r', marker='.', label='prediction')
        ax2.set_xlabel('k ' + ss_labels[1])
        ax2.set_ylabel('k+1 error in ' + ss_labels[1])
        ax2.set_title('predicting k+1 error ' + ss_labels[1])

        ax3 = fig.add_subplot(3,2,3)
        ax3.scatter(self.z_points[:, 2], self.y_points[:, 2], c='k', marker='+', label='training set')
        ax3.scatter(self.z_current[:,2], self.pred_mu[:,2], c='r', marker='.', label='prediction')
        ax3.set_xlabel('k ' + ss_labels[2])
        ax3.set_ylabel('k+1 error in ' + ss_labels[2])
        ax3.set_title('predicting ' + ss_labels[2])
        
        ax4 = fig.add_subplot(3,2,4)
        ax4.scatter(self.z_points[:, 3], self.y_points[:, 3], c='k', marker='+', label='training set')
        ax4.scatter(self.z_current[:,3], self.pred_mu[:,3], c='r', marker='.', label='prediction')
        ax4.set_xlabel('k ' + ss_labels[3])
        ax4.set_ylabel('k+1 error in ' + ss_labels[3])
        ax4.set_title('predicting k+1 error ' + ss_labels[3])

        plt.draw()
        plt.pause(0.01)
        

        
class BangBang(Controller):
    def __init__(self, setpoint, magnitude):
        self.setpoint = setpoint
        self.magnitude = magnitude
    
    def policy(self, state, t):
        error = state[2] - self.setpoint
        if error > 0.1 and state[2] < np.pi/4:
            return self.magnitude
        elif error < -0.1 and state[2] > -np.pi/4:
            return -self.magnitude
        else:
            return 0