import tensorflow as tf
import numpy as np

from tensorflow.python.framework import ops
from tensorflow.python.ops import embedding_ops
from tensorflow.python.framework import constant_op
from tensorflow.python.ops import init_ops
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import nn_ops
from tensorflow.python.ops import control_flow_ops
from tensorflow.python.ops import tensor_array_ops
from tensorflow.python.ops import variable_scope as vs

def permute_tunable(s, L):
    
    helper1 = array_ops.reshape(math_ops.range(1,s+1,2),[-1,1])
    helper2 = array_ops.reshape(math_ops.range(0,s,2),[-1,1])
    ind1 = array_ops.reshape(array_ops.concat([helper1,helper2],1),[1,-1])

    helper1 = array_ops.slice(helper1,[0,0],[(s//2)-1,1])
    helper2 = array_ops.slice(helper2,[1,0],[(s//2)-1,1])
    beginning = array_ops.reshape(0,[1,-1])
    end = array_ops.reshape(s-1,[1,-1])
    ind2 = array_ops.reshape(array_ops.concat([helper2,helper1],1),[-1,1])
    ind2 = array_ops.reshape(array_ops.concat([beginning,ind2,end],0),[1,-1])
    
    ind = array_ops.concat([ind1,ind2],0)
    return ind

def toTensorArray(elems):
    
    elems = ops.convert_to_tensor(elems)
    n = array_ops.shape(elems)[0]
    elems_ta = tensor_array_ops.TensorArray(dtype=elems.dtype, size=n, dynamic_size=False, infer_shape=True, clear_after_read = False)
    elems_ta = elems_ta.unstack(elems)
    return elems_ta


def EUNN_param(hidden_size, capacity=2, FFT=False, comp=False):
    
    theta_phi_initializer = init_ops.random_uniform_initializer(-np.pi, np.pi)

    params_theta_0 = vs.get_variable("theta_0", [int(capacity/2), int(hidden_size/2)], initializer=theta_phi_initializer)
    cos_theta_0 = array_ops.reshape(math_ops.cos(params_theta_0),[-1,1])
    sin_theta_0 = array_ops.reshape(math_ops.sin(params_theta_0),[-1,1])

    params_theta_1 = vs.get_variable("theta_1", [int(capacity/2), int(hidden_size/2)-1], initializer=theta_phi_initializer)
    cos_theta_1 = array_ops.reshape(math_ops.cos(params_theta_1),[-1,1])
    sin_theta_1 = array_ops.reshape(math_ops.sin(params_theta_1),[-1,1])

    diag_list_0 = array_ops.reshape(array_ops.concat([cos_theta_0, cos_theta_0], 1),[1,-1])
    off_list_0 = array_ops.reshape(array_ops.concat([sin_theta_0, -sin_theta_0], 1),[1,-1])
    
    diag_list_1 = array_ops.reshape(array_ops.concat([cos_theta_1, cos_theta_1],1),[1,-1])
    diag_list_1 = array_ops.concat([np.ones((1,1)),diag_list_1,np.ones((1,1))],1)
    
    off_list_1 = array_ops.reshape(array_ops.concat([sin_theta_1, -sin_theta_1],1),[1,-1])
    off_list_1 = array_ops.concat([np.zeros((1,1)),off_list_1,np.zeros((1,1))],1);

    v1 = tf.reshape(tf.concat([diag_list_0, diag_list_1], 1), [capacity, hidden_size])
    v2 = tf.reshape(tf.concat([off_list_0, off_list_1], 1), [capacity, hidden_size])

    v1 = toTensorArray(v1)
    v2 = toTensorArray(v2)
    diag = None
    
    ind = permute_tunable(hidden_size, capacity)
    ind = toTensorArray(ind)
    #ind = None

    return v1, v2, ind, diag, capacity


def EUNN_loop(h, L, v1_list, v2_list, ind_list, D):
    
    i = 0
    def F(x, i):
        v1 = v1_list.read(i)
        v2 = v2_list.read(i)

        diag = math_ops.multiply(x, v1)
        off = math_ops.multiply(x, v2)
      
        type = 2

        if type == 1:
            ind = ind_list.read(i%2)
            off = array_ops.transpose(off)
            off = array_ops.transpose(array_ops.gather(off,ind))
        else:
            s = int(off.get_shape()[1])
            if i%2==0:
                off = array_ops.reshape(off,[-1,s//2,2])
                off = array_ops.reshape(array_ops.reverse_v2(off,[2]),[-1,s])
             
            else:
                helper1, off, helper2 = array_ops.split(off,[1,s-2,1],1)
                off = array_ops.reshape(off,[-1,(s-2)//2,2])
                off = array_ops.reshape(array_ops.reverse_v2(off,[2]),[-1,(s-2)])
                off = array_ops.concat([helper1, off, helper2],1) 
                                                               
        Fx = diag + off                                       
        i += 1                                                
                                                               
        return Fx, i                                          
                                                                   
    def cond (x, i):                                               
        return i < L                                          
                                                                   
    loop_vars = [h, i]                                            
    FFx, _ =  control_flow_ops.while_loop(cond, F, loop_vars)                                                              
                                                                   
    if not D  == None:                                             
         Wx = math_ops.multiply(FFx, D)                        
    else:                                                          
         Wx = FFx                                              
                                                                   
    return Wx                                                     
