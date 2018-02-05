import torch
from torch.autograd import Variable
import torch.nn as nn
import torch.nn.functional as F

'''
Simple, sequential convolutional net.
'''

class Model(nn.Module):
    def __init__(self, input_space, output_space):
        super(Model, self).__init__()

        self.input_space = input_space
        self.output_space = output_space

        self.convs = nn.ModuleList([])
        self.dropouts = nn.ModuleList([]) # Used in dense block

        self.bnorm0 = nn.BatchNorm2d(input_space[-3])
        self.conv1 = self.conv_block(input_space[-3],16)
        self.convs.append(self.conv1)
        self.conv2 = self.conv_block(16, 24, stride=2, bnorm=True)
        self.convs.append(self.conv2)
        self.conv3 = self.conv_block(24, 36, stride=2, bnorm=True)
        self.convs.append(self.conv3)

        self.features = nn.Sequential(*self.convs)
        self.classifier = None


    def conv_block(self, chan_in, chan_out, ksize=3, stride=1, padding=1, activation="relu", max_pool=False, bnorm=True):
        block = []
        block.append(nn.Conv2d(chan_in, chan_out, ksize, stride, padding=padding))
        activation=activation.lower()
        if "relu" in activation:
            block.append(nn.ReLU())
        elif "tanh" in activation:
            block.append(nn.Tanh())
        elif "elu" in activation:
            block.append(nn.ELU())
        elif "selu" in activation:
            block.append(nn.SELU())
        if max_pool:
            block.append(nn.MaxPool2d(2, 2))
        if bnorm:
            block.append(nn.BatchNorm2d(chan_out))
        return nn.Sequential(*block)

    def dense_block(self, chan_in, chan_out, dropout_p=0, activation="relu", batch_norm=True):
        block = []
        dropout = nn.Dropout(dropout_p)
        block.append(dropout)
        self.dropouts.append(dropout)
        block.append(nn.Linear(chan_in, chan_out, bias=False))
        activation=activation.lower()
        if "relu" in activation:
            block.append(nn.ReLU())
        elif "tanh" in activation:
            block.append(nn.Tanh())
        elif "elu" in activation:
            block.append(nn.ELU())
        elif "selu" in activation:
            block.append(nn.SELU())
        if batch_norm:
            block.append(nn.BatchNorm1d(chan_out))
        return nn.Sequential(*block)

    def forward(self, x):
        feats = self.bnorm0(x)
        feats = self.features(feats)
        feats = feats.view(feats.size(0), -1)
        if self.classifier is None:
            modules = [self.dense_block(feats.size(1), 200, batch_norm=False)]
            modules.append(self.dense_block(200, 200, batch_norm=False))
            self.precursor = nn.Sequential(*modules)
            self.classifier = self.dense_block(200,self.output_space,activation="none",batch_norm=False)
            self.evaluator = self.dense_block(200, 1, activation="none", batch_norm=False)
        feats = self.precursor(feats)
        return self.evaluator(feats), self.classifier(feats)

    def add_noise(self, x, mean=0.0, std=0.01):
        """
        Adds a normal distribution over the entries in a matrix.
        """

        means = torch.zeros(*x.size()).float()
        if mean != 0.0:
            means = means + mean
        noise = torch.normal(means,std=std)
        if type(x) == type(Variable()):
            noise = Variable(noise)
        return x+noise

    def multiply_noise(self, x, mean=1, std=0.01):
        """
        Multiplies a normal distribution over the entries in a matrix.
        """

        means = torch.zeros(*x.size()).float()
        if mean != 0:
            means = means + mean
        noise = torch.normal(means,std=std)
        if type(x) == type(Variable()):
            noise = Variable(noise)
        return x*noise

    def calculate_grads(self, calc_bool):
        """
        An on-off switch for the requires_grad parameter for each internal Parameter.

        calc_bool - Boolean denoting whether gradients should be calculated.
        """
        for param in self.parameters():
            param.requires_grad = calc_bool
