# bdt_omnifold_example
Examples of the boosted decision tree OmniFold.

## Environment
To run the examples in this repository, you need the following packages:
- Jupyter Lab
- NumPy
- matplotlib
- energyflow
- scikit-learn

These can all be installed through pip: `pip install jupyterlab numpy matplotlib energyflow scikit-learn`. It is recommended to do this in a virtual environment or Conda environment. To set up a virtual environment, you can do the following:
```
python3 -m venv bdt_omnifold_venv
source bdt_omnifold_venv/bin/activate
pip install -U pip
pip install jupyterlab numpy matplotlib energyflow scikit-learn
```

We will also be using ROOT and RooUnfold. More details can be found on the [ROOT site](https://root.cern/install/) and the [RooUnfold repository](https://gitlab.cern.ch/RooUnfold/RooUnfold), respectively. This repository was created using ROOT version 6.32.02.

## Overview
In the example notebooks in this repository, we demonstrate unfolding using the BDT-based OmniFold with the [Z+jets dataset](https://zenodo.org/records/3548091). We use Pythia as the truth-level and reconstructed Monte Carlo and reconstructed Herwig as the pseudodata. We unfold and aim to recreate the truth-level Herwig. We compare to the results given by RooUnfoldBayes (Iterative Bayesian Unfolding, or IBU) as a baseline.

### Binned unfolding
In the notebook `binned_unfolding.ipynb`, we use response matrices and histograms to do unfolding. We convert these to 2D and 1D NumPy arrays, respectively. To do this, we effectively convert the binned unfolding into an unbinned problem by filling the arrays with the bin centers, repeated with the number of entries in that bin. For instance, for a bin centered at 2.0 with 10 counts, the array will get 10 entries of 2.0. We then use the typical unbinned unfolding procedure. We then bin the final results and correct for efficiency.

### Unbinned unfolding
To be added.
