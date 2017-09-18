import numpy as np
from numpy.matlib import repmat
from skimage.transform import rotate

def create_2D_noise(dim_array=(56,56), beta=-1):
    """
    Function translated by Asier Erramuzpe (@erramuzpe)
    from: https://www.mathworks.com/matlabcentral/fileexchange/5091-generate-spatial-data
    Jon Yearsley  1 May 2004
    j.yearsley@macaulay.ac.uk
   
    This function generates 1/f spatial noise, with a normal error 
    distribution (the grid must be at least 10x10 for the errors to be normal). 
    1/f noise is scale invariant, there is no spatial scale for which the 
    variance plateaus out, so the process is non-stationary.
   
        dim_array is a two component vector that sets the size of the spatial pattern
              (dim_array=[10,5] is a 10x5 spatial grid)
        beta defines the spectral distribution. 
             Spectral density S(f) = N f^beta
             (f is the frequency, N is normalisation coeff).
                  beta = 0 is random white noise.  
                  beta  -1 is pink noise
                  beta = -2 is Brownian noise
            The fractal dimension is related to beta by, D = (6+beta)/2
     
    Note that the spatial pattern is periodic.  If this is not wanted the
    grid size should be doubled and only the first quadrant used.
    Time series can be generated by setting one component of dim_array to 1
    he method is briefly descirbed in Lennon, J.L. "Red-shifts and red
    herrings in geographical ecology", Ecography, Vol. 23, p101-113 (2000)
    
    Many natural systems look very similar to 1/f processes, so generating
    1/f noise is a useful null model for natural systems.
    The errors are normally distributed because of the central
    limit theorem.  The phases of each frequency component are randomly
    assigned with a uniform distribution from 0 to 2*pi. By summing up the
    frequency components the error distribution approaches a normal
    distribution.
    
    # S_f corrected to be S_f = (u.^2 + v.^2).^(beta/2);  2/10/05
    """
    # Generate the grid of frequencies. u is the set of frequencies along the
    # first dimension
    # First quadrant are positive frequencies.  Zero frequency is at u(1,1).
    list_1 = list(range(0, int(np.floor(dim_array[0] / 2)) + 1))
    list_2 = list(range(-int(np.ceil(dim_array[0] / 2) - 1), 0, 1))
    u = np.concatenate((list_1, list_2)) / dim_array[0]
    # Reproduce these frequencies along ever row
    u = np.reshape(repmat(u,1,dim_array[1]), dim_array).T

    # v is the set of frequencies along the second dimension.  For a square
    # region it will be the transpose of u
    list_1 = list(range(0, int(np.floor(dim_array[1] / 2)) + 1))
    list_2 = list(range(-int(np.ceil(dim_array[1] / 2) - 1), 0, 1))
    v = np.concatenate((list_1, list_2)) / dim_array[1]
    # Reproduce these frequencies along ever row
    v = np.reshape(repmat(v,dim_array[0],1), dim_array)


    # Generate the power spectrum
    S_f = np.power(np.power(u,2) + np.power(v,2), (beta/2))
    # Set any infinities to zero
    S_f[np.isinf(S_f)] = 0


    # Generate a grid of random phase shifts
    phi =  np.random.random(dim_array)

    # Inverse Fourier transform to obtain the the spatial pattern
    x = np.fft.ifft2(np.power(S_f, 0.5) * (np.cos(2 * np.pi * phi) + 1j * np.sin(2 * np.pi * phi)))

    # Pick just the real component
    return np.real(x)


def scale_2D(data, scale_range=(0, 255)):
    """
    Scales a 2D np.array between a given range. 0-255 by default
    """
    w, h = data.shape
    data = np.ndarray.flatten(data)
    
    data += -(np.min(data))
    data /= np.max(data) / (scale_range[1] - scale_range[0])
    data += scale_range[0]

    return np.reshape(data, (w, h))


def create_composition(input_image, background_image,
                       x_offset=0, y_offset=0,
                       center=None, radius=0):
    """
    Given an input image and a background image, composes a new frame.
    The input image will be positioned taking into account the offsets.
    The input image will be circularly masked to fade the borders in a gradient
    with the background image, avoiding high contrast borders between the input
    image and the background image.     
    """

    w, h = input_image.shape
    
    # center and radius calculation for input_image
    if center is None:
        center = [int(w/2), int(h/2)]
    if radius is None:
        radius = min(center[0], center[1], w-center[0], h-center[1])

    Y, X = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((X - center[0])**2 + (Y-center[1])**2)

    mask = dist_from_center <= radius

    circle_image = np.ma.array(input_image,
                               mask = ~mask)

    out_image = np.ma.array(input_image,
                            mask = mask).data
    
    out_mask = np.ma.array(dist_from_center,
                           mask = mask)
    out_mask_full = out_mask.copy()
    out_mask_full[out_mask<=radius] = radius
    
    dist_from_center_rescaled = scale_2D(out_mask_full.data,
                                         scale_range=(0, 1))

    background_offset = background_image[y_offset:y_offset+w, x_offset:x_offset+h]

    background_fade = background_offset * dist_from_center_rescaled + out_image
    new_input_image = background_fade + circle_image
    
    background_image[y_offset:y_offset+w, x_offset:x_offset+h] = new_input_image

    return background_image


def create_new_dataset(dataset, offsets=[[0,0]], rotate=False, degree=None):
    """
    Creates dataset for training/testing different configurations.
    It will locate images (m,n) in 2*m length/width frame in the given offsets
    and rotated if rotate argument is true.
    The degree argument is to select the rotation degree. Given by None for random
    selection and degree*90º if int. 
    """
    
    m, n = dataset.shape
    im_x = int(np.sqrt(n))
    num_offsets = len(offsets)
    
    new_dataset = np.zeros((m, n*4))
    
    for i in range(m):
        image = np.reshape(dataset[i,:], (im_x, im_x))
        if rotate is not False:
            image = rotate_image(image, rot=degree)
        noise_bg = scale_2D(create_2D_noise())
        
        rand_offset = np.random.randint(0, num_offsets)

        result = create_composition(image, noise_bg,
                       x_offset=offsets[rand_offset][0],
                       y_offset=offsets[rand_offset][1],
                       center=None, radius=None)
        
        new_dataset[i,:] = np.ndarray.flatten(result)
        
    return new_dataset


def rotate_image(image, angle=None):
    """
    Function to rotate given image to left side by angle degrees
    """
    
    if angle is None:
        angle = np.random.randint(0, 360)

    return rotate(image, angle=angle)