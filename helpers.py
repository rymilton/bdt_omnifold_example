import numpy as np
def get_substructure_obs(dataset):
    feature_names = ['widths','mults','sdms','zgs','tau2s']
    gen_features = [dataset['gen_jets'][:,3]]
    sim_features = [dataset['sim_jets'][:,3]]
    for feature in feature_names:
        gen_features.append(dataset['gen_'+feature])
        sim_features.append(dataset['sim_'+feature])


    gen_features = np.stack(gen_features,-1)
    sim_features = np.stack(sim_features,-1)
    #ln rho
    gen_features[:,3] = 2*np.ma.log(np.ma.divide(gen_features[:,3],dataset['gen_jets'][:,0]+10**-100).filled(0)).filled(0)
    sim_features[:,3] = 2*np.ma.log(np.ma.divide(sim_features[:,3],dataset['sim_jets'][:,0]+10**-100).filled(0)).filled(0)
    #tau21
    gen_features[:,5] = gen_features[:,5]/(10**-50 + gen_features[:,1])
    sim_features[:,5] = sim_features[:,5]/(10**-50 + sim_features[:,1])

    return sim_features, gen_features