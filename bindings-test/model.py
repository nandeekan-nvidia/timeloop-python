import sys

from bindings import (Config, ConfigNode, ArchConstraints, invoke_accelergy,
                      ArchProperties, ArchSpecs, Mapping, Workload, Engine)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class TimeloopModelApp:
    def __init__(self, cfg: Config, out_dir: str, verbose=False,
                 auto_bypass_on_failure=False, out_prefix=''):
        root_node = cfg.get_root()

        # Use defaults for now
        self.verbose = verbose
        self.auto_bypass_on_failure = auto_bypass_on_failure
        self.out_prefix = out_prefix
        semi_qualified_prefix = 'timeloop-model'
        self.out_prefix = out_dir + '/' + semi_qualified_prefix

        if 'model' in root_node:
            model = root_node['model']
            self.verbose = model['verbose']
            self.auto_bypass_on_failure = model['auto_bypass_on_failure']
            semi_qualified_prefix = model['out_prefix']

        # TODO: print banner if verbose

        # Problem configuration
        prob_cfg = root_node['problem']
        self.workload = Workload()
        self.workload.parse_workload(prob_cfg)
        if self.verbose:
            print('Problem configuration complete.')

        # Architecture configuration
        if 'arch' in root_node:
            arch_cfg = root_node['arch']
        elif 'architecture' in root_node:
            arch_cfg = root_node['architecture']
        self.arch_specs = ArchSpecs.parse_specs(arch_cfg)

        if 'ERT' in root_node:
            if self.verbose:
                print('Found Accelergy ERT, replacing internal energy model')
            self.arch_specs.parse_accelergy_ert(root_node['ert'])
            if 'ART' in root_node:
                if self.verbose:
                    print('Found Accelergy ART, replacing internal area model')
                self.arch_specs.parse_accelergy_art(root_ndoe['art'])
        else:
            if 'subtree' in arch_cfg or 'local' in arch_cfg:
                print('Invoking Accelergy')
                invoke_accelergy(cfg.in_files, semi_qualified_prefix, out_dir)
                ert_path = self.out_prefix + '.ERT.yaml'
                # Have to store config in a variable, so it doesn't get
                # garbage collected. CompoundConfigNode referes to it.
                ert_cfg = Config(ert_path)
                ert = ert_cfg.get_root().lookup('ERT')
                if self.verbose:
                    print('Generated Accelergy ERT to replace internal energy '
                          'model')
                self.arch_specs.parse_accelergy_ert(ert)

                art_path = self.out_prefix + '.ART.yaml'
                art_cfg = Config(art_path)
                art = art_cfg.get_root()['ART']
                if self.verbose:
                    print('Generated Accelergy ART to replace internal energy '
                          'model')
                self.arch_specs.parse_accelergy_art(art)

        self.arch_props = ArchProperties(self.arch_specs)

        # Architecture constraints
        constraints_cfg = ConfigNode()
        if 'constraints' in arch_cfg:
            constraints_cfg = arch_cfg['constraints']
        elif 'arch_constraints' in arch_cfg:
            constraints_cfg = arch_cfg['arch_constraints']
        elif 'architecture_constraints' in arch_cfg:
            constraints_cfg = arch_cfg['architecture_constraints']

        self.constraints = ArchConstraints(self.arch_props, self.workload)
        self.constraints.parse(constraints_cfg)

        if verbose:
            print('Architecture configuration complete.')

        # Mapping configuration
        mapping_cfg = root_node['mapping']
        self.mapping = Mapping.parse_and_construct(
            mapping_cfg, self.arch_specs, self.workload)
        if verbose:
            print('Mapping construction complete.')

        # Validate mapping against architecture constraints
        if not self.constraints.satisfied_by(self.mapping):
            print('ERROR: mapping violates architecture constraints.')
            exit(1)

    def run(self):
        stats_fname = self.out_prefix + 'stats.txt'
        xml_fname = self.out_prefix + '.map+stats.xml'
        map_xml_fname = self.out_prefix + '.map.txt'

        engine = Engine()
        engine.spec(self.arch_specs)

        level_names = self.arch_specs.level_names()

        if self.auto_bypass_on_failure:
            pre_eval_stat = engine.pre_evaluation_check(
                self.mapping, self.workload, False)
            for level, status in enumerate(pre_eval_stat):
                if not status.success and self.verbose:
                    eprint("ERROR: couldn't map level ", level_names[level],
                           ': ', pre_eval_stat[level].fail_reason,
                           ', auto-bypassing.')
                if not status.success:
                    for pvi in range(get_problem_shape().num_data_spaces):
                        # TODO: bind mapping.datatype_bypass_nest
                        pass

        eval_stat = engine.evaluate(self.mapping, self.workload)
        for level, status in enumerate(eval_stat):
            if not status.success:
                eprint("ERROR: couldn't map level ", level_names[level], ': ',
                       pre_eval_stat[level].fail_reason)
                exit(1)

        if engine.is_evaluated():
            print('Utilization = ', engine.utilization(), ' | pJ/MACC',
                  engine.energy() / engine.get_topology().maccs())
            # TODO: bind Topology::TileSizes


if __name__ == '__main__':
    import glob

    prefix = '../timeloop-accelergy-exercises/exercises/timeloop/00-model-conv1d-1level/'
    input_files = []
    for input_dir in ['arch/', 'map/', 'prob/']:
        input_files += glob.glob(prefix + input_dir + '*')
    config = Config(input_files)

    app = TimeloopModelApp(config, '.', verbose=True)
    app.run()
