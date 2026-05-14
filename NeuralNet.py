#NeuralNet.py

import torch as tc
import torch.nn as nn

class LayerStuff(nn.Module):
    def __init__(self, numin,numout):
        super().__init__()
        self.actLayer = nn.Linear(numin,numout)
        self.e = tc.zeros_like(self.actLayer.weight)
        nn.init.normal_(self.actLayer.weight, 0, 0.1)
        self.actfn = nn.LeakyReLU(0.01)
    def forward(self,x, out: bool):
        if out:
            y = tc.sigmoid(self.actLayer(x))
        else:
            y = self.actfn(self.actLayer(x))
        self.lx = x.detach()
        self.ly = y.detach()
        return y
    def UpdateE(self, dec): 
        self.e = dec * self.e + tc.outer(self.ly, self.lx) 
        self.e = self.e / (self.e.norm(dim=1, keepdim=True) + 1e-6)



class Network(nn.Module):
    def __init__(self):
        super().__init__()
        self.lays = []
    def AddLayer(self,l : LayerStuff):
        self.lays.append(l)
    def BuildNetwork(self):
        self.layers = nn.ModuleList(self.lays)

    def forward(self, x):
        for i, layer in enumerate(self.layers):
            out = (i == len(self.layers) - 1)
            x = layer(x, out)
        return x

    def UpdateE(self, dec):
        for layer in self.layers:
            layer.UpdateE(dec)


def SurrogateBuild():
    brain = Network()
    brain.AddLayer(LayerStuff(8,16))
    brain.AddLayer(LayerStuff(16,4))
    brain.AddLayer(LayerStuff(4,1))
    brain.BuildNetwork()
    return brain






