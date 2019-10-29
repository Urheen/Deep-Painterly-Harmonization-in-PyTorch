# EECS 442 @ UMich Final Project 
# No commercial Use Allowed 

import os 
import torch 
import torch.nn as nn 
import torch.optim as optim 
import torchvision.transforms as transforms 
import torchvision.models as models
import torchvision
import torch.nn.functional as F 
from PIL import Image 
import argparse
import copy
import math 
import numpy as np 
import scipy.interpolate as interpolate
import matplotlib.pyplot as plt


def setup(cfg):
    if cfg.gpu == -1:
        dtype, device = torch.FloatTensor, "cpu"
    else:
        dtype, device = torch.cuda.FloatTensor, "cuda:"+str(cfg.gpu)

    if cfg.debug_mode:
        print('===>setup()')
        print('device', device)
        print('dtype', dtype)

    return dtype, device

def save_img_plt(img, path, gray=False):
    '''
    Input : 1 * 1 * H * W / 1 * 3 * H * W Tensor 
    '''
    print('===>save image')
    print(path)
    print('img shape', img.shape)

    img = img.cpu().numpy()
    img = img * 255 
    if not gray:
        img = np.dstack([img[0,0,:,:], img[0,1,:,:], img[0,2,:,:]])
    else:
        img = img.squeeze((0,1))
    plt.figure()
    if not gray:
        plt.imshow(img)
    else:
        plt.imshow(img ,cmap='Greys_r')
    plt.colorbar()
    plt.savefig(path)
    plt.close()


def mask_preprocess(mask_file, out_shape, dtype, device, cfg, name='mask_preprocess.png'):
    '''
    Return : 1 * 1 * H * W Tensor for mask 
    '''
    mask = Image.open(mask_file).convert('L')

    if type(out_shape) is not tuple:
        out_shape = tuple([int((float(out_shape) / max(mask.size))*x) for x in (mask.height, mask.width)])

    transform = transforms.Compose([
        transforms.Resize(out_shape),
        transforms.ToTensor()
    ])

    mask = transform(mask)
    mask = mask.to(device)
    mask = mask.type(dtype)
    mask[mask != 0] = 1
    mask = mask.unsqueeze(0)

    if cfg.debug_mode:
        print('===>mask_preprocess')
        print('for {}'.format(str(mask_file)))
        print('output range : ', (torch.min(mask), torch.max(mask)))
        print('output shape : ', mask.shape)
        save_img_plt(mask, name, gray=True)

    return mask 


def img_preprocess(img_file, out_shape, dtype, device, cfg, name='img_preprocess.png'):
    '''
    Return : 1 * 3 * H * W Tensor for image  
    '''
    img = Image.open(img_file).convert('RGB')

    if type(out_shape) is not tuple:
        out_shape = tuple([int((float(out_shape) / max(img.size))*x) for x in (img.height, img.width)])

    transform = transforms.Compose([
        transforms.Resize(out_shape),
        transforms.ToTensor(),
    ])
    normalize = transforms.Normalize(mean=[103.939, 116.779, 123.68], std=[1,1,1])

    img = transform(img)
    img = normalize(img*256)
    img = img.to(device)
    img = img.type(dtype)
    img = img.unsqueeze(0)

    if cfg.debug_mode:
        print('===>img_preprocess')
        print('for {}'.format(str(img_file)))
        print('output range : ', (torch.min(img), torch.max(img)))
        print('output shape : ', img.shape)
        save_img_plt(img, name)

    return img
    
    