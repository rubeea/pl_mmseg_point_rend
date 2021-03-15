import torch
import torch.nn as nn
import torch.nn.functional as F

from ..builder import LOSSES
from .utils import weight_reduce_loss, reduce_loss
from .cross_entropy_loss import _expand_onehot_labels


def phi_loss(inputs, targets, gamma, smooth, weight=None, reduction='mean',
                  avg_factor=None):
    
    inputs = inputs.sigmoid()
    targets= targets.type_as(inputs)
    
    # flatten label and prediction tensors
    inputs = inputs.view(-1)
    targets = targets.view(-1)
    weight= weight.view(-1)
    
    #removing .sum() to keep the tensor dimensions to [2,2,256,256] compatible with weight dimensions
    # to use .sum with TP,FP and FN, weights must also be summed using .sum() in weighted reduction loss
  
    # print(gamma)
    # print(inputs)
    # print(targets)
    
    TP = (inputs * targets).sum()
    FP = ((1 - targets) * inputs).sum()
    FN = (targets * (1 - inputs)).sum()
    TN= inputs[targets==0.].sum()
    
    phi = ((TP * TN - FP * FN) + smooth) / torch.sqrt((TP + FP) * (TP + FN) * (TN + FP) * (TN + FN) + smooth) 
    loss= (1. - phi) ** gamma #focal_phi_loss
    loss= reduce_loss(loss,reduction=reduction)
    return loss


@LOSSES.register_module()
class PhiLoss(nn.Module):
    """PhiLoss.

    Args:
        reduction (str, optional): . Defaults to 'mean'.
            Options are "none", "mean" and "sum".
        smooth (float, optional): Smoothing factor. Defaults to 1.0.
        loss_weight (float, optional): Weight of the loss. Defaults to 1.0.
    """

    def __init__(self,
    			 gamma= 1.0,
                 reduction='mean',
                 smooth=1,
                 loss_weight=1.0):
        super(PhiLoss, self).__init__()
        self.gamma = gamma
        self.reduction = reduction
        self.loss_weight = loss_weight
        self.smooth = smooth

    def forward(self,
                inputs,
                targets,
                weight=None,
                reduction_override=None,
                avg_factor=None,
                ignore_index=255):
        """Forward function."""
        assert reduction_override in (None, 'none', 'mean', 'sum')
        reduction = (
            reduction_override if reduction_override else self.reduction)
        # print(inputs.shape) #[2,2,256,256] => [N,C,H,W]
        # print(targets.shape) #[2,256,256] => [N,H,W]

        if inputs.dim() != targets.dim():
            assert (inputs.dim() == 2 and targets.dim() == 1) or (
                inputs.dim() == 4 and targets.dim() == 3), \
            'Only pred shape [N, C], label shape [N] or pred shape [N, C, ' \
            'H, W], label shape [N, H, W] are supported'
            label, weight = _expand_onehot_labels(targets, weight, inputs.shape,
                                                ignore_index) #use imported version from cross_entropy_loss
        phi_loss_val= phi_loss(inputs, label, self.gamma, self.smooth,
                               weight, reduction= reduction, avg_factor=avg_factor 
                              )
        # print(phi_loss_val)
        loss = self.loss_weight * phi_loss_val
        # print(loss)
        return loss
