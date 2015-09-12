# Copyright (C) 2012 Robert Lanfear and Brett Calcott
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# PartitionFinder also includes the PhyML program, the RAxML program, and the
# PyParsing library, all of which are protected by their own licenses and
# conditions, using PartitionFinder implies that you agree with those licences
# and conditions as well.

import logtools
import pandas
log = logtools.get_logger()
from config import the_config
from model_utils import get_raxml_protein_modelstring


import os

scheme_header_template = "%-18s: %s\n"
scheme_subset_template = "%-6s | %-10s | %-10s | %-32s | %-100s\n"
subset_template = "%-15s | %-15s | %-15s | %-15s  | %-15s | %-15s\n"

# We write different output for these searches
_odd_searches = ['kmeans']

class TextReporter(object):
    def __init__(self, config):
        self.cfg = config
        self.cfg.reporter = self

    def write_subset_summary(self, sub):
        pth = os.path.join(self.cfg.subsets_path, sub.subset_id + '.txt')
        # Sort everything

        cols = ['model_id', 'params', 'lnl', 'aicc', 'aic', 'bic']

        descr = self.cfg.data_layout.data_type.descr
        indices = dict([(t[0], i) for i, t in enumerate(descr) if t[0] in cols])

        sorted_results = [(row['aicc'], row) for row in sub.result_array]
        sorted_results.sort()


        output = open(pth, 'w')
        output.write("Model selection results for subset: %s\n" % sub.subset_id)
        if sub.alignment_path:
            output.write("Subset alignment stored here: %s\n" % sub.alignment_path)
        if the_config.search not in _odd_searches:
            output.write("This subset contains the following data_blocks: %s\n" % sub.name)
        output.write("Number of columns in subset: %d\n" % len(sub.columns))
        output.write("Models are organised according to their AICc scores\n\n")

        output.write(subset_template % ("Model", "Parameters", "lNL", "AICc", "AIC", "BIC"))
        for aicc, row in sorted_results:
            output.write(subset_template % (row[indices['model_id']], 
                                            row[indices['params']], 
                                            row[indices['lnl']], 
                                            row[indices['aicc']], 
                                            row[indices['aic']],
                                            row[indices['bic']]))  


    def write_scheme_summary(self, sch, result):
        pth = os.path.join(self.cfg.schemes_path, sch.name + '.txt')
        output = open(pth, 'w')
        self.output_scheme(sch, result, output)

    def output_scheme(self, sch, result, output):
        self.write_scheme_header(sch, result, output)
        sorted_subsets = [sub for sub in sch]
        sorted_subsets.sort(key=lambda sub: min(sub.columns), reverse=False)
        self.write_subsets(sch, result, output, sorted_subsets)
        self.write_nexus_summary(output, sorted_subsets)
        self.write_raxml(sch, result, output, sorted_subsets)

    def write_scheme_header(self, sch, result, output):
        output.write(scheme_header_template % ("Scheme Name", sch.name))
        output.write(scheme_header_template % ("Scheme lnL", result.lnl))
        if self.cfg.model_selection == "aic":
            output.write(scheme_header_template % ("Scheme AIC", result.aic))
        if self.cfg.model_selection == "aicc":
            output.write(scheme_header_template % ("Scheme AICc", result.aicc))
        if self.cfg.model_selection == "bic":
            output.write(scheme_header_template % ("Scheme BIC", result.bic))
        output.write(scheme_header_template % ("Number of params", result.sum_k))
        output.write(scheme_header_template % ("Number of sites", result.nsites))
        output.write(scheme_header_template % ("Number of subsets", result.nsubs))
        output.write("\n")

    def write_nexus_summary(self, output, sorted_subsets):
        output.write("\n\nNexus formatted character sets\n")
        output.write("begin sets;\n")

        subset_number = 1
        charpartition = []
        for sub in sorted_subsets:
            if self.cfg.search in _odd_searches:
                sites = [x + 1 for x in sub.columns]
                partition_sites = str(sites).strip('[]')
            else:
                partition_sites = sub.site_description

            output.write("\tcharset Subset%s = %s;\n" % (subset_number, partition_sites))
            charpartition.append("Group%s:Subset%s" % (subset_number, subset_number))
            subset_number += 1
        output.write('\tcharpartition PartitionFinder = %s;\n' % ', '.join(charpartition))
        output.write('end;\n')

    def write_subsets(self, sch, result, output, sorted_subsets):
        
        output.write(scheme_subset_template % (
            "Subset", "Best Model", "# sites", "subset id", "Partition names"))
        number = 1
        # a way to print out the scheme in PF format
        pf_scheme_description = []
            
        if self.cfg.search in _odd_searches:
            for sub in sorted_subsets:
                num_sites = len(sub.columns)
                
                sites = [x + 1 for x in sub.columns]
                pf_scheme_description.append("(%s)" % str(sites).strip('[]'))
                output.write(scheme_subset_template % (
                    number, 
                    sub.best_model, 
                    num_sites,
                    sub.subset_id, 
                    'NA',
                    ))
                number += 1

        else:
            for sub in sorted_subsets:
                pf_scheme_description.append("(%s)" % sub.name)
                output.write(scheme_subset_template % (
                    number, 
                    sub.best_model, 
                    len(sub.columns), 
                    sub.subset_id, 
                    sub.name,
                    ))
                number += 1

        
        pf_scheme_description = " ".join(pf_scheme_description)
        output.write("\n\nScheme Description in PartitionFinder format\n")
        output.write("Scheme_%s = %s;" % (sch.name, pf_scheme_description))

    def write_raxml(self, sch, result, output, sorted_subsets):
        """Print out partition definitions in RaxML-like format, might be
        useful to some people
        """
        output.write("\n\nRaxML-style partition definitions\n")

        subset_number = 1
        for sub in sorted_subsets:
            if self.cfg.search in _odd_searches:
                sites = [x + 1 for x in sub.columns]
                partition_sites = str(sites).strip('[]')
            else:
                partition_sites = sub.site_description

            if self.cfg.datatype == "DNA":
                model = 'DNA'
            elif self.cfg.datatype == "protein":
                model = get_raxml_protein_modelstring(sub.best_model)
            else:
                raise RuntimeError

            output.write("%s, Subset%s = %s" % (model, subset_number, partition_sites))
            output.write("\n")
            subset_number += 1

        output.write("\nWarning: RAxML allows for only a single model of rate"
                     " heterogeneity in partitioned analyses. I.e. all "
                     "partitions must be assigned either a +G model or a "
                     "+I+G model. If the best models for your dataset"
                     "contain both types of model, you will need to choose "
                     "an appropriate rate heterogeneity model when you run "
                     "RAxML. This is specified through the command line to "
                     "RAxML. To rigorously choose the best model, run two "
                     "further PF analyses (these will be fast), fixing "
                     "the partitioning scheme to this scheme and "
                     "'search=user;', in both. In one run, use only +I+G "
                     "models ('models = all_protein_gammaI'); in the next, "
                     "use only +G models ('models = all_protein_gamma;''). "
                     "Choose the scheme with the lowest AIC/AICc/BIC score. "
                     "Note that these re-runs will be quick!" 
                    )

    def write_best_scheme(self, result):
        pth = os.path.join(self.cfg.output_path, 'best_scheme.txt')
        output = open(pth, 'wb')
        output.write('Settings used\n\n')
        output.write(scheme_header_template % ("alignment", self.cfg.alignment_path))
        output.write(scheme_header_template % ("branchlengths", self.cfg.branchlengths))
        output.write(scheme_header_template % ("models", ', '.join(self.cfg.models)))
        output.write(scheme_header_template % ("model_selection",
                                                self.cfg.model_selection))
        output.write(scheme_header_template % ("search", self.cfg.search))
        if self.cfg.search in ["rcluster", "hcluster"]:
            pretty_weights = "rate = %s, base = %s, model = %s, alpha = %s" %(
                               str(self.cfg.cluster_weights["rate"]),
                               str(self.cfg.cluster_weights["freqs"]),
                               str(self.cfg.cluster_weights["model"]),
                               str(self.cfg.cluster_weights["alpha"]))
            output.write(scheme_header_template % ("weights", pretty_weights))

        if self.cfg.search == "rcluster":
            output.write(scheme_header_template % ("rcluster-percent",
                                                   self.cfg.cluster_percent))
            output.write(scheme_header_template % ("rcluster-max",
                                                       self.cfg.cluster_max))

        if self.cfg.search == "kmeans":
            output.write(scheme_header_template % ("min-subset-size",
                                                   self.cfg.min_subset_size))
            output.write(scheme_header_template % ("kmeans based on",
                                                   self.cfg.kmeans))

        output.write('\n\nBest partitioning scheme\n\n')
        self.output_scheme(result.best_scheme, result.best_result, output)
        log.info("Information on best scheme is here: %s", pth)

        citation_text = write_citation_text(self)

        # now we write subset summaries for all the subsets in the best scheme
        for s in result.best_scheme:
            self.write_subset_summary(s)

        log.info("\n")
        log.info("\n")

        for c in citation_text:
            log.info("%s", c)
            output.write(c)



def write_citation_text(self):
    """Tell users which papers to cite"""

    citation_text = []

    ref_PF2 = ("Lanfear, R., Calcott, B., Frandsen, P. Forthcoming. "
             "PartitionFinder 2: new methods for selecting partitioning "
             "schemes and models of molecular evolution for large datasets. "
             "In preparation.")

    ref_PF1 = ("Lanfear, R., Calcott, B., Ho, S. Y., & Guindon, S. (2012). "
             "PartitionFinder: combined selection of partitioning schemes "
             "and substitution models for phylogenetic analyses. "
             "Molecular biology and evolution, 29(6), 1695-1701.")

    ref_rcluster = ("Lanfear, R., Calcott, B., Kainer, D., Mayer, C., "
                    "& Stamatakis, A. (2014). Selecting optimal "
                    "partitioning schemes for phylogenomic datasets. "
                    "BMC evolutionary biology, 14(1), 82.")

    ref_kmeans = ("Frandsen, P. B., Calcott, B., Mayer, C., & Lanfear, R. "
                  "(2015). Automatic selection of partitioning schemes for "
                  "phylogenetic analyses using iterative k-means clustering "
                  "of site rates. BMC Evolutionary Biology, 15(1), 13.")

    ref_phyml = ("Guindon, S., Dufayard, J. F., Lefort, V., Anisimova, M., "
                 "Hordijk, W., & Gascuel, O. (2010). New algorithms and "
                 "methods to estimate maximum-likelihood phylogenies: "
                 "assessing the performance of PhyML 3.0. "
                 "Systematic biology, 59(3), 307-321.")

    ref_raxml = ("Stamatakis, A. (2014). RAxML version 8: a tool for "
                 "phylogenetic analysis and post-analysis of large phylogenies. "
                 "Bioinformatics, 30(9), 1312-1313.")

    citation_text.append("\n\n\n*Citations for this analysis*\n")
    citation_text.append("-----------------------------")

    citation_text.append("\n")

    citation_text.append("If you use this analysis in your published "
        "work, please cite "
        "the following papers on which your analysis relied.\n")

    citation_text.append("\n")
    citation_text.append("For the version of PartitionFinder you used, "
                         "please cite:\n")

    citation_text.append("%s\n" % ref_PF2)

    citation_text.append("\n")
    citation_text.append("For the %s algorithm you used, please cite:\n" 
                         % (self.cfg.search))

    if self.cfg.search == "rcluster" or self.cfg.search == "hcluster":
        citation_text.append("%s\n" % ref_rcluster)

    elif self.cfg.search == "kmeans":
        citation_text.append("%s\n" % ref_kmeans)

    elif self.cfg.search == "greedy":
        citation_text.append("%s\n" % ref_PF1)

    citation_text.append("\n")
    if self.cfg.phylogeny_program == 'phyml':
        citation_text.append("Your analysis also used PhyML, so please cite:\n")
        citation_text.append("%s\n" % ref_phyml)

    elif self.cfg.phylogeny_program == 'raxml':
        citation_text.append("Your analysis also used RAxML, so please cite:\n")
        citation_text.append("%s\n" % ref_raxml)
    citation_text.append("\n")

    return citation_text