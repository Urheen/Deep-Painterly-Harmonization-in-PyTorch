# EECS 442 @ UMich Final Project 
# No commercial Use Allowed 

import os 
import torch 
import torch.nn as nn 
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
import sys 

def init_log(cfg):
    orig_stdout = sys.stdout

    if cfg.log_on == 'on':
        print('\n==> Log setup to log.txt')
        sys.stdout = open('log.txt','w')

    message = "Deep Painterly Harmonization log file\n\
    \'===>\' : Begin of Specific Stage \n\
    \'\' : Sub-operation inside stage \n\
    \'@\' : Time Spend in that stage"

    print(message)
    return orig_stdout

def end_log(orig_stdout):
    sys.stdout.close()
    sys.stdout=orig_stdout 

def setup(cfg):

    if cfg.gpu == 'cpu':
        dtype, device = torch.FloatTensor, "cpu"
    else:
        dtype, device = torch.cuda.FloatTensor, "cuda:"+str(cfg.gpu)

    
    print('\n===> Device Datatype Setup')
    print('device', device)
    print('dtype', dtype)

    return dtype, device


def get_args():
    parser = argparse.ArgumentParser()
    # Input Output
    parser.add_argument("-style_image", help="./path/file to style image", default='data/0_target.jpg')
    parser.add_argument("-content_image", help="./path/file to simple stich image", default='data/0_naive.jpg')
    parser.add_argument("-inter_image", help="./path/file to intermediate image", default='official_result/0_inter_res.jpg')
    parser.add_argument("-tight_mask", help="./path/file to tight mask", default='data/0_c_mask.jpg')
    parser.add_argument("-dilated_mask", help="./path/file to dilated(loss) mask", default='data/0_c_mask_dilated.jpg')
    parser.add_argument("-output_img", help="./path/file for output image", default='output/0_pass1_out.png')
    parser.add_argument("-output_img_size", help="Max side(H/W) for output image, power of 2 is recommended", type=int,
                        default=512)

    # Training Parameter
    parser.add_argument("-optim", choices=['lbfgs', 'adam'], default='adam') # lbfgs currently not support 
    parser.add_argument("-lr", type=float, default=1e0)
    parser.add_argument("-n_iter", type=int, default=1000)
    parser.add_argument("-print_interval", type=int, default=150) 
    parser.add_argument("-save_img_interval", type=int, default=50)
    parser.add_argument("-gpu", help="Zero-indexed ID of the GPU to use; for CPU mode set -gpu = cpu", default='cpu')

    # Model Parameter
    parser.add_argument("-content_layers", help="layers for content", default='relu4_2')
    parser.add_argument("-style_layers", help="layers for style", default='relu3_1,relu4_1,relu5_1') # Layer choice for Deep Paintely Harmonization 
    #parser.add_argument("-style_layers", help="layers for style", default='relu1_1,relu2_1,relu3_1,relu4_1,relu5_1') # Layer choice for A Neural Algorithm of Artistic Style by Leon A. Gatys
    parser.add_argument("-histogram_layers", help="layers for histogram loss, only use for pass2", default='relu1_1,relu4_1') # Not used in pass1
    parser.add_argument("-content_weight", type=float, default=5e0)
    parser.add_argument("-style_weight", type=float, default=1e2) 
    parser.add_argument("-tv_weight", type=float, default=1e-3)
    parser.add_argument("-histogram_weight", type=float, default=0) # For pass 2, commonly use '1e2'
    parser.add_argument('-mse_loss_outside_mask_weight', type=float, default=1) # For DIP ANALYSIS 
    parser.add_argument('-mse_loss_within_mask_weight', type=float, default=1e2) # For DIP ANALYSIS 
    parser.add_argument("-model_file", help="path/file to saved model file, if not will auto download", default='./download_model_weight/vgg19-d01eb7cb.pth')
    parser.add_argument("-model", choices=['vgg16', 'vgg19'], default='vgg19')
    parser.add_argument("-match_patch_size", type=int, default=3)
    parser.add_argument("-generator_model", choices=['skip_depth6', 'skip_depth4', 'skip_depth2', 'UNET', 'ResNet']) # For DIP ANALYSIS 
    parser.add_argument("-noise_input_depth", type=int, default=1) # input depth for noise input to generator model 

    # Other 
    parser.add_argument('-log_on', choices=['on', 'off'], default='off') # if 'on' is choose, redirect output to log file 
    parser.add_argument('-log_file', help='log file name', default='log.txt')
    parser.add_argument('-verbose', help='print_information', action='store_true') # Print loss information during training or not

    cfg = parser.parse_args()

    print('\n===> Configuration Setup')
    print('style loss layer', cfg.style_layers)
    print('content loss layer', cfg.content_layers)
    print('histogram loss layer', cfg.histogram_layers)

    return cfg


#def build_optimizer(cfg, img):
#    '''
#    Input:
#        img : Tensor type image with require_grad = True
#            can be build by passing image through `img = nn.Parameter(img)`
#    '''
#    # optimizer = torch.optim.SGD(model.parameters(), lr = 0.001)
#    assert(img.requires_grad==True)
#    if cfg.optim == 'adam':
#        optimizer = torch.optim.Adam([img], cfg.lr)
#    elif cfg.optim == 'lbfgs':
#        # TODO lbfgs optimizer setup is different then Adam, setup this 
#        optimizer = None
#    else:
#        # TODO raise error that optimizer type not support 
#        return None
#    
#    return optimizer


def mask_preprocess(mask_file, out_shape):
    '''
    Return : 
        1 * 1 * H * W [0. - 1.] Tensor for mask 
    Notice : 
        NO CONVERSINO OF TYPE / DEVICE IS DONE IN THIS FUNCTION 
    '''
    mask = Image.open(mask_file).convert('L')

    if type(out_shape) is not tuple:
        out_shape = tuple([int((float(out_shape) / max(mask.size))*x) for x in (mask.height, mask.width)])

    transform = transforms.Compose([
        transforms.Resize(out_shape),
        transforms.ToTensor() # [0.-1.]
    ])

    mask = transform(mask)
    mask[mask != 0] = 1
    mask = mask.unsqueeze(0)

    return mask 


def img_preprocess(img_file, out_shape, norm=True):
    '''
    Input:
        img_file : file name to image 
        output_shape : 
        norm : if norm, normalize image to [0. - 255.]
               if not norm, return image in range [0. - 1.] without normalization 
    Return : 
        if norm : 1 * 3 * H * W [0. - 255.] Tensor for image  (used in this project)
        if not norm : 1 * 3 * H * W [0. - 1.] Tensor for image  (used for further exploration)
    Notice:
        NO CONVERSINO OF TYPE / DEVICE IS DONE IN THIS FUNCTION 
    Explain : 
        random initialize network tend to produce value in range [0. - 1.] and hard to mimin image in range [0. - 255.].
            thus output image in range [0. - 1.] if using random initialize network to output image (DIP)
    '''
    img = Image.open(img_file).convert('RGB')

    if type(out_shape) is not tuple:
        out_shape = tuple([int((float(out_shape) / max(img.size))*x) for x in (img.height, img.width)])

    transform = transforms.Compose([
        transforms.Resize(out_shape),
        transforms.ToTensor(),
    ])
    rgb2bgr = transforms.Compose([transforms.Lambda(lambda x: x[torch.LongTensor([2,1,0])])])
    normalize = transforms.Normalize(mean=[103.939, 116.779, 123.68], std=[1,1,1])

    if norm:
        img = rgb2bgr(transform(img) * 256)
        img = normalize(img)
    else:
        img = rgb2bgr(transform(img))

    img = img.unsqueeze(0)

    return img # [0. - 255.]


def img_deprocess(img_tensor, norm=True):
    '''
    Input : 
        img_tensor : 
            if norm 1 * 3 * H * W [0.-255.] Tensor represent the updated image 
            if not norm 1 * 3 * H * W [0. - 1.] Tensor represent the updated image without normalization 
        norm : 
            if norm : resize to [0. - 1.]
            if not norm : do nothing 
    Notice : 
        REMEMBER to clone() the value when given as input to this function 
    Return : 
        PIL.Image 
    '''
    de_normalize = transforms.Normalize(mean=[-103.939, -116.779, -123.68], std=[1,1,1])
    bgr2rgb = transforms.Compose([transforms.Lambda(lambda x: x[torch.LongTensor([2,1,0])])])

    img_tensor = img_tensor.squeeze(0).cpu()
    if norm:
        img_tensor = de_normalize(img_tensor)
        img_tensor = bgr2rgb(img_tensor / 256)
    else:
        img_tensor = bgr2rgb(img_tensor)
    img_tensor.clamp_(0, 1)

    img = transforms.ToPILImage()(img_tensor)

    return img 


def preprocess(cfg, dtype, device, norm=True):
    '''
    Return : 
        img : 1 * 3 * H * W , Tensor, (to(device), .type(dtype))
        mask : 1 * 1 * H * W, Tensor, (to(device), .type(dtype))
    '''
    content_img = img_preprocess(cfg.content_image, cfg.output_img_size, norm=norm).type(dtype).to(device) # 1 * 3 * H * W [0.-255.]
    img_size = (content_img.shape[2], content_img.shape[3]) 
    style_img = img_preprocess(cfg.style_image, img_size, norm=norm).type(dtype).to(device) # 1 * 3 * H * W [0.-255.]
    inter_img = img_preprocess(cfg.inter_image, img_size).type(dtype).to(device) # 1 * 3 * H * W [0.-255.]s
    tight_mask = mask_preprocess(cfg.tight_mask, img_size).type(dtype).to(device) # 1 * 1 * H * W [0/1]
    loss_mask = mask_preprocess(cfg.dilated_mask, img_size).type(dtype).to(device) # 1 * 1 * H * W [0/1]
    print('\n===> Preprocess Image and Mask')
    print('img shape', content_img.shape)
    print('mask shape', loss_mask.shape)

    return content_img, style_img, inter_img, tight_mask, loss_mask


def conv2d_same_padding(input, filter, stride=1):
    '''
    :param input: 1 * C * H * W
    :param filter: 1 * C * F * F
    :param stride:
    :return: output: 1 * C * H * W
    '''
    _, _, H, W = input.shape

    out_rows = (H + stride - 1) // stride
    padding_rows = max(0, (out_rows - 1) * stride + filter.shape[2] - H)
    rows_odd = (padding_rows % 2 != 0)
    out_cols = (W + stride - 1) // stride
    padding_cols = max(0, (out_cols - 1) * stride + filter.shape[3] - W)
    cols_odd = (padding_rows % 2 != 0)

    if rows_odd or cols_odd:
        input = F.pad(input, [0, int(cols_odd), 0, int(rows_odd)])

    return F.conv2d(input, filter, stride=stride, padding=(padding_rows // 2, padding_cols // 2))


def plt_plot_loss(style_loss_his, content_loss_his, tv_loss_his, histogram_loss_his, name=''):
    assert(len(style_loss_his) == len(content_loss_his))
    x = np.arange(len(style_loss_his))
    c_his = plt.plot(x, content_loss_his, label='Content Loss')
    s_his = plt.plot(x, style_loss_his, label='Style Loss')
    if len(tv_loss_his) != 0:
        assert(len(tv_loss_his) == len(style_loss_his))
        tv_his = plt.plot(x, tv_loss_his, label='TV Loss')
    if len(histogram_loss_his) != 0:
        assert(len(histogram_loss_his) == len(style_loss_his))
        h_his = plt.plot(x, histogram_loss_his, label='Histogram Loss')
    
    plt.title('Loss History')
    plt.xlabel('Iteration')
    plt.ylabel('Loss')
    plt.legend(loc = "best")
    plt.savefig(name+'loss_history.png')


def dilate_mask(mask):
    '''
    Function : given tight mask, get dialated mask (loss mask)
    '''
    loose_mask = cv2.GaussianBlur(mask, (35,35) , 35/3)
    loose_mask[loose_mask>=0.1] = 1
    return loose_mask


def tight_mask_crop(cfg, result, style_img, tight_mask):
    '''
    Input:
        result (Tensor) : tensor that represent result of image after being updated
    '''
    assert(result.shape == style_img.shape)
    tight_mask = tight_mask.expand_as(style_img)
    output = tight_mask * result + (1 - tight_mask) * style_img

    output_filename, file_extension = os.path.splitext(cfg.output_img)
    filename = str(output_filename) + '_cropped_'+str(file_extension)
    output_deprocessed = img_deprocess(output.clone())
    output_deprocessed.save(str(filename))

    return output
