import numpy as np
import matplotlib.pyplot as plt
import itertools

from tqdm.notebook import tqdm, trange

import torch
from torch.utils.data import DataLoader
nn = torch.nn

import nmastandard as nmas

class AE(nn.Module):
  def __init__(self, in_dim, latent_dim, enc_lst, dec_lst):
    """
    Initialize AutoEncoder
    ---
    Parameters:
    * in_dim : Number of input dimensions
    * latent_dim : Size of latent space
    * enc_lst : List of number of hidden nodes at each encoder layer
    * dec_lst : List of number of hidden nodes at each decoder layer
    """

    super(AE, self).__init__()

    self.in_dim = in_dim
    self.out_dim = in_dim

    # Create Encoder Model
    layers_a = [[nn.Linear(in_dim, enc_lst[0], bias=True), nn.ReLU()]]
    layers_a += [[nn.Linear(enc_lst[idim], enc_lst[idim+1], bias=True), nn.ReLU()] for idim in range(len(enc_lst)-1)]
    layers_a += [[nn.Linear(enc_lst[-1], latent_dim, bias=True)]]
    enc_layers = []
    for layer in layers_a:
      enc_layers += layer
    self.enc_model = nn.Sequential(*enc_layers)


    # Create Decoder Model
    layers_a = [[nn.Linear(latent_dim, dec_lst[0], bias=True), nn.ReLU()]]
    layers_a += [[nn.Linear(dec_lst[idim], dec_lst[idim+1], bias=True), nn.ReLU()] for idim in range(len(dec_lst)-1)]
    layers_a += [[nn.Linear(dec_lst[-1], in_dim, bias=True)]]
    dec_layers = []
    for layer in layers_a:
      dec_layers += layer
    self.dec_model = nn.Sequential(*dec_layers)

  def encode(self, x):
    '''
    Enocdes x into the latent space
    ---
    Parameters:
    * x (torch.tensor) : The dataset to encode (size: num_examples x in_dim)

    Returns:
    * l (torch.tensor) : Projection into the latent space of original data (size: num_examples x latent_dim)
    '''
    return self.enc_model(x)

  def decode(self, l):
    '''
    Decode l from the latent space into the initial dataset
    ---
    Parameters:
    * l (torch.tensor) : The encoded latent space representation (size: num_examples x latent_dim)

    Returns:
    * x (torch.tensor) : Approximation of the original dataset encoded (size: num_examples x in_dim)
    '''
    return self.dec_model(l)

  def forward(self, x):
    '''
    Feed raw dataset through encoder -> decoder model in order to generate overall approximation from latent space
    ---
    Parameters:
    * x (torch.tensor) : The dataset to encode (size: num_examples x in_dim)

    Returns:
    * x (torch.tensor) : Approximation of the original dataset from the encoded latent space (size: num_examples x in_dim)
    '''
    flat_x = x.view(x.size(0), -1)
    h = self.encode(flat_x)
    return self.decode(h).view(x.size())

def train_autoencoder(autoencoder, dataset, device, val_dataset=None, epochs=20, batch_size=250,
                      seed=0):
  '''
  Train the provided "autoencoder" model on the provided tensor dataset.
  ---
  Parameters:
  * autoencoder (AE) : AE model to train
  * dataset (torch.tensor) : The dataset to encode (size: num_examples x in_dim)
  * device (str) : Device to use for training ('cuda' or 'cpu')
  * val_dataset (torch.tensor) : The datset to encode for validation loss (size: num_examples x in_dim)
  * epochs (int) : Number of iterations through the entire dataset on which to train
  * batch_size (int) : Number of examples in randomly sampled batches to pass through the model
  * seed (int) : Random seed to use for the model

  Returns:
  * mse_loss (torch.tensor) : List of Mean Squared Error losses by training timestep
  '''

  autoencoder.to(DEVICE)
  optim = torch.optim.Adam(autoencoder.parameters(),
                           lr=1e-2,
                           #weight_decay=1e-5
                           )
  loss_fn = nn.MSELoss()
  g_seed = torch.Generator()
  g_seed.manual_seed(seed)
  loader = DataLoader(dataset,
                      batch_size=batch_size,
                      shuffle=True,
                      pin_memory=True,
                      num_workers=2,
                      worker_init_fn=nmas.seed_worker,
                      generator=g_seed)
  

  mse_loss = torch.zeros(epochs * len(dataset) // batch_size, device=device)
  
  full_mse_loss = torch.zeros(epochs, device=device)
  if val_dataset is not None:
    full_val_loss = torch.zeros(epochs, device=device)
  else:
    full_val_loss = None
  
  i = 0
  for epoch in trange(epochs, desc='Epoch'):
    # print(len(list(itertools.islice(loader, 1))))
    for im_batch in loader:
      im_batch = im_batch.to(device)
      optim.zero_grad()
      reconstruction = autoencoder(im_batch)
      # write the loss calculation
      loss = loss_fn(reconstruction.view(batch_size, -1),
                    target=im_batch.view(batch_size, -1))
      loss.backward()
      optim.step()

      mse_loss[i] = loss.detach()
      i += 1


    with torch.no_grad():
      fim_batch = dataset.to(device)
      freconstruction = autoencoder(fim_batch)
      floss = loss_fn(freconstruction.view(fim_batch.size(0), -1),
                      target=fim_batch.view(fim_batch.size(0), -1))
      full_mse_loss[epoch] = floss.detach()
      
      if val_dataset is not None:
          val_im_batch = val_dataset.to(device)
          val_reconstruction = autoencoder(val_im_batch)
          val_loss = loss_fn(val_reconstruction.view(val_im_batch.size(0), -1),
                            target=val_im_batch.view(val_im_batch.size(0), -1))
          full_val_loss[epoch] = val_loss.detach()
    

    if epoch % 10 == 0:
      print(f'MSE Train Loss @ {epoch}: {full_mse_loss[epoch]}')
      if val_dataset is not None:
        print(f'MSE Val Loss @ {epoch}: {full_val_loss[epoch]}')
  
  # After training completes, make sure the model is on CPU so we can easily
  # do more visualizations and demos.
  autoencoder.to('cpu')

  tr_mse = full_mse_loss.cpu()
  val_mse = full_val_loss.cpu() if val_dataset is not None else None

  return tr_mse, val_mse

if __name__ == '__main__':
    SEED = 2021
    nmas.set_seed(seed=SEED)
    DEVICE = nmas.set_device()

    
    x_a = np.random.choice(10000, size=10000)
    tmp = np.tile(np.arange(-1,2), (x_a.shape[0],1))
    x = np.tile(x_a.reshape(-1,1), [1, 3]) + tmp

    inx = np.random.choice(x.shape[0])
    
    x = torch.tensor(x).float()

    x_tr = x[:-x.size(0)//5]
    x_val = x[-x.size(0)//5:]

    vae = AE(x.size(-1), 1, [5], [5])
    loss, val_loss = train_autoencoder(vae, x_tr, DEVICE, epochs=20, batch_size=250, seed=0)

    print(f'Final Training Loss: {loss}')
    print(f'Final Validation Loss: {val_loss}')