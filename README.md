# Project_Deep_Painterly_Harmonization

> EECS 442 Final Project at University of Michigan, Ann Arbor
> 
> Reimplementatino of paper `Deep Painterly Harmonization` 



Pytorch implementation of paper "[Deep Painterly Harmonization](https://arxiv.org/abs/1804.03189)"  


Official code written in Torch and lua can be found here [Github Link](https://github.com/luanfujun/deep-painterly-harmonization)


This PyTorch implementation follow the structure of [Neural Style Pt Github Link]() where the network is first build and feature map is captured after the architrcture is build. In the original code [Github Link](https://github.com/luanfujun/deep-painterly-harmonization), the feature map is captured during the build of architecture which cause waist of computation. Also, the loss in different layer back prop by simply adding them up and call `loss_total.backward()` where in the offitial code, a backward hook is build to pass the loss gradient (`function StyleLoss:updateGradInput`)


**This Repo is still under active develop and have not yet finish**


## TODO 

1. StyleLossPass2 

2. (sx) StyleLossPass1 

3. (sx) Pass 1 debug & test validation 

4. pass 2 

5. (sx) notebook for bp work on mask area [DONE]

6. (sx) periodic save, periodic print [DONE]

7. need to check in the original lua code, what does `dG:div(msk:sum())` is doing, why divide the gradient, how can this be acapted into out code. 
