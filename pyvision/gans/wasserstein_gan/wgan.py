# -*- coding: utf-8 -*-
"""WGAN.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1yvxYIYP8fgS1g_kUySqvSgbGhDLqiRnx

Imports
"""

#!ls

from __future__ import print_function
import torchvision.datasets as dset
import torchvision.transforms as transforms
import torch.utils.data as data_utils
import random
import torch
import os
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.optim as optim
import torch.utils.data
import torchvision.utils as vutils
from torch.utils.data import Dataset, DataLoader, TensorDataset
import matplotlib
matplotlib.use('agg')
from matplotlib import rcParams
rcParams['font.family'] = 'sans-serif'
rcParams['font.sans-serif'] = ['Arial']
import matplotlib.pyplot as plt
import numpy as np
import datetime

"""Transforms"""

nc = 3 # Number of Channels 3 for RGB
nz = 100 # Size of Latent vector i.e input to Generator
ngf = 64 # Number of generator filters
ndf = 64 # Number of generator filters
batch_size = 64 #batch_size
dataroot = 'datasets' # Dataset must contain a subdirectory which contains the images. "dir/subdir/img.png"

def load_dataset():


   workers = 6 #Number of workers, If you dont have a high end cpu it is best to be left at 2

   trans = transforms.Compose([transforms.Resize(64),
                            transforms.ToTensor(),
                            transforms.Normalize((0.5, 0.5, 0.5), (0.5,0.5,0.5))])

   dataset = dset.ImageFolder(root = dataroot , transform = trans) #dataroot = path/to/save_data


   assert dataset

   dataloader = torch.utils.data.DataLoader(dataset, batch_size= batch_size
                                            , num_workers=workers)
   return dataloader

def clear_line():
    """Clear line from any characters"""
    print('\r{}'.format(' ' * 80), end='\r')



def format_hdr(gan, root_dir, training_len):

    num_params_D, num_params_G = gan.get_num_params()
    gan_type = 'Wasserstein GAN (WGAN)'
    gan_loss = 'min_G max_D  E_x[D(x)] - E_z[D(G(z))]'
    title = 'Wasserstein Generative Adversarial Network (GAN)'.center(80)
    sep, sep_ = 80 * '-', 80 * '='
    type_str = 'Type: {}'.format(gan_type)
    loss_str = 'Loss: {}'.format(gan_loss)
    param_D_str = 'Nb of generator params: {:,}'.format(num_params_D)
    param_G_str = 'Nb of discriminator params: {:,}'.format(num_params_G)
    dataset = 'Training on  dataset ({}) with {:,} Images'.format(root_dir, training_len)
    hdr = '\n'.join([sep_, title, sep, dataset, type_str, loss_str, param_G_str, param_D_str, sep_])
    print(hdr)



def time_elapsed_since(start):
    """Compute elapsed time since start"""

    end = datetime.datetime.now()
    return str(end - start)[:-7]


def progress_bar(batch_idx, report_interval, G_loss, D_loss):
    """Neat progress bar to track training"""

    bar_size = 24
    progress = (((batch_idx - 1) % report_interval) + 1) / report_interval
    fill = int(progress * bar_size)
    print('\rBatch {:>4d} [{}{}] G loss: {:>7.4f} | D loss: {:>7.4f}'.format(batch_idx, '=' * fill, ' ' * (bar_size - fill), G_loss, D_loss), end='')



def show_learning_stats(batch_idx, num_batches, g_loss, d_loss, elapsed):
    """Format stats"""

    clear_line()
    dec = str(int(np.ceil(np.log10(num_batches))))
    print('Batch {:>{dec}d} / {:d} | G loss: {:>7.4f} | D loss: {:>7.4f} | Avg time / batch: {:d} ms'.format(batch_idx, num_batches, g_loss, d_loss, int(elapsed), dec=dec))


def unnormalize(img):
    return (img.data + 1) / 2.0


def plot_error_bars():
    """ Plot error bar graph """

    N = 2
    gan_means = (2.7355, 2.3357)
    gan_std = (0.1558, 0.1417)

    ind = np.arange(N)  # the x locations for the groups
    width = 0.25       # the width of the bars

    fig, ax = plt.subplots()
    rects1 = ax.bar(ind, gan_means, width, color='#8290F9', yerr=gan_std)

    wgan_means = (2.8347, 2.2646)
    wgan_std = (0.1736, 0.1270)
    rects2 = ax.bar(ind + width, wgan_means, width, color='#CDD1FE', yerr=wgan_std)

    # add some text for labels, title and axes ticks
    ax.set_ylabel('Score',fontsize=16)
    ax.set_xticks(ind + width / 2)
    ax.set_xticklabels(('Inception', 'Mode'),fontsize=16)
    for tick in ax.yaxis.get_major_ticks():
        tick.label.set_fontsize(12)

    ax.legend((rects1[0], rects2[0]), ('GAN', 'WGAN'), loc="upper right", fontsize=16)
    plt.tight_layout()
    plt.savefig('score.png', dpi=200)


class AvgMeter(object):
    """Compute and store the average and current value"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0.
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count

#device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')


"""Init"""

class WGAN(nn.Module):
  def __init__(self, nz = nz, batch_size = batch_size, device="cpu"):
    super().__init__()
    self.nz = nz
    self.batch_size = batch_size
    self.G = Generator(nz,ngf, nc)
    self.D = Discriminator(nc, ndf)
    self.init_weights(self.G)
    self.init_weights(self.D)
    self.y_real = torch.ones(batch_size)
    self.y_fake = torch.zeros(batch_size)
    #if torch.cuda.is_available():
    if device is not "cpu":
        if not torch.cuda.is_available():
            raise ValueError("CUDA not available but device=", device)
        self.device = torch.device("cuda")
    else:
        self.device = torch.device("cpu")
    self.y_real = self.y_real.to(device) #change
    self.y_fake = self.y_fake.to(device) #change

  def load_model(self, filename):
      """Load PyTorch model"""

      print('Loading generator checkpoint from: {}'.format(filename))
      self.G.load_state_dict(torch.load(filename, map_location = self.device))

  def save_model(self, ckpt_path, epoch, override=True):
      """Save model"""
      self.gan_type = "WGAN"
      if override:
          fname_gen_pt = '{}/{}-gen.pt'.format(ckpt_path, self.gan_type)
          fname_disc_pt = '{}/{}-disc.pt'.format(ckpt_path, self.gan_type)
      else:
          fname_gen_pt = '{}/{}-gen-epoch-{}.pt'.format(ckpt_path, self.gan_type, epoch + 1)
          fname_disc_pt = '{}/{}-disc-epoch-{}.pt'.format(ckpt_path, self.gan_type, epoch + 1)

      print('Saving generator checkpoint to: {}'.format(fname_gen_pt))
      torch.save(self.G.state_dict(), fname_gen_pt)
      sep = '\n' + 80 * '-'
      print('Saving discriminator checkpoint to: {}{}'.format(fname_disc_pt, sep))
      torch.save(self.D.state_dict(), fname_disc_pt)

  def init_weights(self, model):
        """Initialize weights and biases (according to paper)"""

        for m in model.parameters():
            if isinstance(m, nn.ConvTranspose2d) or isinstance(m, nn.Conv2d):
                m.weight.data.normal_(0, 0.02)
                m.bias.data.zero_()


  def get_num_params(self):
        """Compute the total number of parameters in model"""

        num_params_D, num_params_G = 0, 0
        for p in self.D.parameters():
            num_params_D += p.data.view(-1).size(0)
        for p in self.G.parameters():
            num_params_G += p.data.view(-1).size(0)
        return num_params_D, num_params_G


  def create_latent_var(self, batch_size, seed=None):
        """Create latent variable z"""

        if seed:
            torch.manual_seed(seed)
        z = torch.randn(batch_size, self.nz)
        #if torch.cuda.is_available():
        z = z.to(self.device)
        return z
  def train_G(self, G_optimizer, batch_size):
    self.G.zero_grad()
    self.D.zero_grad()

    z = self.create_latent_var(self.batch_size)
    fake_imgs = self.G(z)
    D_out_fake = self.D(fake_imgs)
    G_train_loss = -D_out_fake.mean()
    G_train_loss.backward()
    G_optimizer.step()
    G_loss = G_train_loss.item()
    return G_loss

  def train_D(self, x, D_optimizer, batch_size):
    """Update discriminator parameters"""

    self.D.zero_grad()

    # Through generator, then discriminator
    D_out_real = self.D(x)
    z = self.create_latent_var(self.batch_size)
    fake_imgs = self.G(z).detach()
    D_out_fake = self.D(fake_imgs)
    D_train_loss = -(D_out_real.mean() - D_out_fake.mean())
    D_train_loss.backward()
    D_optimizer.step()
    self.D.clip()
    D_loss = D_train_loss.item()
    return D_loss, fake_imgs

  def generate_img(self, z=None, n=1, seed=None):
        """Sample random image from GAN"""
        # Nothing was provided, sample
        if z is None and seed is None:
            z = self.create_latent_var(n)
        # Seed was provided, use it to sample
        elif z is None and seed is not None:
            z = self.create_latent_var(n, seed)
        return self.G(z)

"""Network Architecture"""

class Generator(nn.Module):
  def __init__(self, nz = nz, ngf = ngf, nc = nc):
    super().__init__()
    self.linear = nn.Sequential(
        nn.Linear(nz, ngf*8*4*4, bias = False),
        nn.BatchNorm1d(ngf*8*4*4),
        nn.ReLU(True))
    self.features = nn.Sequential(
        nn.ConvTranspose2d(ngf*8, ngf*4,4, 2, 1, bias = False),
        nn.BatchNorm2d(ngf*4),
        nn.ReLU(True),
        nn.ConvTranspose2d(ngf*4, ngf*2,4, 2, 1, bias = False),
        nn.BatchNorm2d(ngf*2),
        nn.ReLU(True),
        nn.ConvTranspose2d(ngf*2, ngf,4, 2, 1, bias = False),
        nn.BatchNorm2d(ngf),
        nn.ReLU(True),
        nn.ConvTranspose2d(ngf, nc, 4, 2, 1, bias=False),
        nn.Tanh()
    )
  def forward(self, x):
    x = self.linear(x).view(x.size(0),-1,4,4)
    return self.features(x)

class Discriminator(nn.Module):
      def __init__(self, nc = nc, ndf = ndf):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(nc, ndf, 4, 2, 1),
            nn.LeakyReLU(0.2, inplace = True),
            nn.Conv2d(ndf, ndf*2, 4, 2, 1),
            nn.BatchNorm2d(ndf*2),
            nn.LeakyReLU(0.2, inplace = True),
            nn.Conv2d(ndf*2, ndf*4, 4, 2, 1),
            nn.BatchNorm2d(ndf*4),
            nn.LeakyReLU(0.2, inplace = True),
            nn.Conv2d(ndf*4, ndf*8, 4, 2, 1),
            nn.BatchNorm2d(ndf*8),
            nn.LeakyReLU(0.2, inplace = True),
            nn.Conv2d(ndf*8, 1, 4, 1)

        )
      def forward(self, x):
           return self.features(x).view(-1)

      def clip(self, c=0.01):  # Weights clamping value
        """Weight clipping in (-c, c)"""

        for p in self.parameters():
            p.data.clamp_(-c, c)