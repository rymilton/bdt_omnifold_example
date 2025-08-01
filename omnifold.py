import ROOT
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
import pickle
import os

def TH1_to_numpy(hist):
    num_bins = hist.GetNbinsX()
    hist_counts = np.empty(num_bins)
    bin_centers = np.empty(num_bins)
    bin_widths = np.empty(num_bins)
    for i in range(num_bins):
        hist_counts[i] = hist.GetBinContent(i+1)
        bin_centers[i] = hist.GetBinCenter(i+1)
        bin_widths[i] = hist.GetBinWidth(i+1)
    return hist_counts, bin_centers, bin_widths

def TH2_to_numpy(hist):
    num_X_bins = hist.GetNbinsX()
    num_Y_bins = hist.GetNbinsY()
    hist_counts = np.empty(shape=(num_X_bins, num_Y_bins))
    bin_centers = np.empty(shape=(num_X_bins, num_Y_bins), dtype=object)
    bin_widths = np.empty(shape=(num_X_bins, num_Y_bins), dtype=object)
    for i in range(num_X_bins):
        for j in range(num_Y_bins):
            hist_counts[i, j] = hist.GetBinContent(i+1, j+1)
            bin_center_tuple = (hist.GetXaxis().GetBinCenter(i+1), hist.GetYaxis().GetBinCenter(j+1))
            bin_centers[i, j] = bin_center_tuple
            bin_width_tuple = (hist.GetXaxis().GetBinWidth(i+1), hist.GetYaxis().GetBinWidth(j+1))
            bin_widths[i, j] = bin_width_tuple
    return hist_counts, bin_centers, bin_widths

def prepare_hist_data(counts, bin_centers, bin_widths):
    out_array = np.empty(shape=(int(np.sum(counts)), 1))
    out_weights = np.empty(shape=(int(np.sum(counts)), 1))
    entry_tracker = 0
    for (count, bin_center, bin_width) in zip(counts, bin_centers, bin_widths):
        out_array[entry_tracker:int(entry_tracker+count)] = bin_center
        out_weights[entry_tracker:int(entry_tracker+count)] = bin_width
        entry_tracker += int(count)
    return out_array, out_weights

def prepare_response_data(counts, bin_centers, bin_widths):
    MCgen_array = np.empty(shape=(int(np.sum(counts)), 1))
    MCreco_array = np.empty(shape=(int(np.sum(counts)), 1))
    MCgen_weights = np.empty(shape=(int(np.sum(counts)), 1))
    MCreco_weights = np.empty(shape=(int(np.sum(counts)), 1))
    entry_tracker = 0
    for (count, bin_center, bin_width) in zip(counts, bin_centers, bin_widths):
        MCreco_array[entry_tracker:int(entry_tracker+count)] = bin_center[0]
        MCgen_array[entry_tracker:int(entry_tracker+count)] = bin_center[1]
        MCreco_weights[entry_tracker:int(entry_tracker+count)] = bin_width[0]
        MCgen_weights[entry_tracker:int(entry_tracker+count)] = bin_width[1]
        entry_tracker += int(count)
    return MCgen_array, MCreco_array, MCgen_weights, MCreco_weights

def reweight(events, classifier):
    class_probabilities = classifier.predict_proba(events)
    data_probability = class_probabilities[:,1]
    weights = data_probability / (1. - data_probability)
    return np.squeeze(np.nan_to_num(weights))

def omnifold(
        MCgen_entries,
        MCreco_entries,
        measured_entries,
        MC_pass_reco_mask,
        MC_pass_truth_mask,
        measured_pass_reco_mask,
        num_iterations,
        MCgen_weights = None,
        MCreco_weights = None,
        measured_weights = None,
        classifier1_params = {},
        classifier2_params = {},
        regressor_params = {},
        save_models = False,
        model_save_name = "bdt_unbinned_omnifold",
        model_save_path = "./weights/",
    ):
    # Removing events that don't pass generation level cuts
    MCreco_entries = MCreco_entries[MC_pass_truth_mask]
    MCgen_entries = MCgen_entries[MC_pass_truth_mask]
    MC_pass_reco_mask = MC_pass_reco_mask[MC_pass_truth_mask]
    if MCgen_weights is not None:
        MCgen_weights = MCgen_weights[MC_pass_truth_mask]
    else:
        MCgen_weights = np.ones(len(MCgen_entries))
    if MCreco_weights is not None:
        MCreco_weights = MCreco_weights[MC_pass_truth_mask]
    else:
        MCreco_weights = np.ones(len(MCreco_entries))
    if measured_weights is None:
        measured_weights = np.ones(len(measured_entries))
    
    measured_labels = np.ones(len(measured_entries[measured_pass_reco_mask]))
    MC_labels = np.zeros(len(MCgen_entries))

    weights_pull = np.ones(len(MCgen_entries))
    weights_push = np.ones(len(MCgen_entries))

    step1_classifier = GradientBoostingClassifier(**classifier1_params)
    step2_classifier = GradientBoostingClassifier(**classifier2_params)
    use_regressor =  any(~MC_pass_reco_mask)
    if use_regressor:
        step1_regressor = GradientBoostingRegressor(**regressor_params)

    if save_models:
        if not os.path.exists(model_save_path):
            print(f"Path {model_save_path} not found. This path will be created.")
            os.makedirs(model_save_path, exist_ok=True)
        else:
            print(f"Saving models to existing path {model_save_path}")
    
    for i in range(num_iterations):
        print(f"Starting iteration {i+1} step 1")
        step1_data = np.concatenate((MCreco_entries[MC_pass_reco_mask], measured_entries[measured_pass_reco_mask]))
        step1_labels = np.concatenate((np.zeros(len(MCreco_entries[MC_pass_reco_mask])), measured_labels))
        step1_weights = np.concatenate(
            (weights_push[MC_pass_reco_mask]*MCreco_weights[MC_pass_reco_mask], 
            np.ones(len(measured_entries[measured_pass_reco_mask]))*measured_weights[measured_pass_reco_mask])
        )
        
        # Training step 1 classifier and getting weights
        step1_classifier.fit(step1_data, step1_labels, sample_weight = step1_weights)
        new_weights = np.ones_like(weights_pull)
        new_weights[MC_pass_reco_mask] = reweight(MCreco_entries[MC_pass_reco_mask], step1_classifier)
        
        # Training a regression model to predict the weights of the events that don't pass reconstruction
        if use_regressor:
            step1_regressor.fit(MCgen_entries[MC_pass_reco_mask], new_weights[MC_pass_reco_mask])
            new_weights[~MC_pass_reco_mask] = step1_regressor.predict(MCgen_entries[~MC_pass_reco_mask])
        weights_pull = np.multiply(weights_push, new_weights)

        if save_models:
            step1_models = {"step1_classifier": step1_classifier}
            if use_regressor:
                step1_models['step1_regressor'] = step1_regressor
            file = os.path.join(model_save_path, f"{model_save_name}_iter{i+1}_step1.pkl")
            with open(file, "wb") as outfile:
                pickle.dump(step1_models, outfile)
            
        # Training step 2 classifier
        print(f"Starting iteration {i+1} step 2")
        step2_data = np.concatenate((MCgen_entries, MCgen_entries))
        step2_labels = np.concatenate((MC_labels, np.ones(len(MCgen_entries))))
        step2_weights = np.concatenate((np.ones(len(MCgen_entries))*MCgen_weights, weights_pull*MCgen_weights))
        step2_classifier.fit(step2_data, step2_labels, sample_weight = step2_weights)

         # Getting step 2 weights and storing iteration weights
        weights_push = reweight(MCgen_entries, step2_classifier)
        
        if save_models:
            step2_models = {"step2_classifier": step2_classifier}
            file = os.path.join(model_save_path, f"{model_save_name}_iter{i+1}_step2.pkl")
            with open(file, "wb") as outfile:
                pickle.dump(step2_models, outfile)
        
    return weights_pull, weights_push


def binned_omnifold(response_hist, measured_hist, num_iterations, use_density=False):
    measured_counts, measured_bin_centers, measured_bin_widths = TH1_to_numpy(measured_hist)
    response_counts, response_bin_centers, response_bin_widths = TH2_to_numpy(response_hist)
    MCgen_entries, MCreco_entries, MCgen_weights, MCreco_weights = prepare_response_data(response_counts.flatten(), response_bin_centers.flatten(), response_bin_widths.flatten())
    measured_entries, measured_weights = prepare_hist_data(measured_counts, measured_bin_centers, measured_bin_widths)
    # use_density option will use the bin widths as weights if it's True
    if not use_density:
        MCgen_weights = np.ones_like(MCgen_weights)
        MCreco_weights = np.ones_like(MCreco_weights)
        measured_weights = np.ones_like(measured_weights)
    MC_pass_reco_mask = np.full(MCgen_entries.shape[0], True)
    MC_pass_truth_mask = np.full(MCreco_entries.shape[0], True)
    measured_pass_reco_mask = np.full(measured_entries.shape[0], True)
    _, step2_weights = omnifold(MCgen_entries,
                                MCreco_entries,
                                measured_entries,
                                MC_pass_reco_mask,
                                MC_pass_truth_mask,
                                measured_pass_reco_mask,
                                num_iterations,
                                MCgen_weights = MCgen_weights.flatten(),
                                MCreco_weights = MCreco_weights.flatten(),
                                measured_weights = measured_weights.flatten())
    unfolded_hist = ROOT.TH1D("unfolded_hist",
                            "unfolded_hist",
                            response_hist.GetNbinsY(),
                            response_hist.GetYaxis().GetBinLowEdge(1),
                            response_hist.GetYaxis().GetBinLowEdge(response_hist.GetNbinsY())
                            +response_hist.GetYaxis().GetBinWidth(response_hist.GetNbinsY())
                            )
    for (weight, MC) in zip(step2_weights, MCgen_entries.flatten()):
        unfolded_hist.Fill(MC, weight)

    return unfolded_hist
def unbinned_omnifold(
        MCgen_entries,
        MCreco_entries,
        measured_entries,
        num_iterations,
        MC_pass_reco_mask = None,
        MC_pass_truth_mask = None,
        measured_pass_reco_mask = None,
        MCgen_weights = None,
        MCreco_weights = None,
        measured_weights = None,
        classifier1_params={},
        classifier2_params={},
        regressor_params={},
        save_models=True,
        model_save_name="bdt_unbinned_omnifold",
        model_save_path = "./weights/",
    ):
    if MCgen_entries.ndim == 1:
        MCgen_entries = np.expand_dims(MCgen_entries, axis = 1)
    if MCreco_entries.ndim == 1:
        MCreco_entries = np.expand_dims(MCreco_entries, axis = 1)
    if measured_entries.ndim == 1:
        measured_entries = np.expand_dims(measured_entries, axis = 1)
    if MC_pass_reco_mask is None:
        MC_pass_reco_mask = np.full(MCgen_entries.shape[0], True, dtype=bool)
    if MC_pass_truth_mask is None:
        MC_pass_truth_mask = np.full(MCgen_entries.shape[0], True, dtype=bool)
    if measured_pass_reco_mask is None:
        measured_pass_reco_mask = np.full(measured_entries.shape[0], True, dtype=bool)
    return omnifold(
        MCgen_entries,
        MCreco_entries,
        measured_entries,
        MC_pass_reco_mask,
        MC_pass_truth_mask,
        measured_pass_reco_mask,
        num_iterations,
        MCgen_weights,
        MCreco_weights,
        measured_weights,
        classifier1_params,
        classifier2_params,
        regressor_params,
        save_models,
        model_save_name,
        model_save_path,
    )

def get_step1_predictions(MCgen_data, MCreco_data, model_save_directory = "./weights/", model_name = "bdt_unbinned_omnifold", iteration = 4, pass_reco = None):
    file = os.path.join(model_save_directory, f"{model_name}_iter{iteration}_step1.pkl")
    if os.path.isfile(file):
        print(f"Opening {file} for step 1 predictions.")
    else:
        raise ValueError(f"{file} does not exist!")
    with open(file, "rb") as infile:
        loaded_models = pickle.load(infile)
    step1_test_weights = np.ones(len(MCreco_data))
    if pass_reco is None or len(pass_reco)==0:
        pass_reco = np.full_like(step1_test_weights, True, dtype=bool)
    if MCreco_data.ndim == 1:
        MCreco_data = np.expand_dims(MCreco_data, axis = 1)
    if MCgen_data.ndim == 1:
        MCgen_data = np.expand_dims(MCgen_data, axis = 1)
    step1_test_weights[pass_reco] = reweight(MCreco_data[pass_reco], loaded_models['step1_classifier'])
    if any(~pass_reco):
        step1_test_weights[~pass_reco] = loaded_models['step1_regressor'].predict(MCgen_data[~pass_reco])
    return step1_test_weights

def get_step2_predictions(MCgen_data, model_save_directory = "./weights/", model_name = "bdt_unbinned_omnifold", iteration = 4):
    file = os.path.join(model_save_directory, f"{model_name}_iter{iteration}_step2.pkl")
    if os.path.isfile(file):
        print(f"Opening {file} for step 2 predictions.")
    else:
        raise ValueError(f"{file} does not exist!")
    with open(file, "rb") as infile:
        loaded_models = pickle.load(infile)
    if MCgen_data.ndim == 1:
        MCgen_data = np.expand_dims(MCgen_data, axis = 1)
    step2_test_weights = reweight(MCgen_data, loaded_models['step2_classifier'])
    return step2_test_weights