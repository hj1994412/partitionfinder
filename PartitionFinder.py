import logging, os
curdir, f = os.path.split(__file__)
config_path = os.path.join(curdir, 'logging.cfg')
from logging import config as _logconfig
_logconfig.fileConfig(config_path)

log = logging.getLogger("main")

from optparse import OptionParser
import sys

from partfinder import config, analysis, util, parser


def main():
    usage = """usage: python %prog [options] <foldername>

    PartitionFinder is designed to discover optimal partitioning schemes for
    DNA sequence alignments. It it also useful for finding the best model of
    sequence evolution for one or more partitions.

    The Input: <foldername>: the full path to a folder containing:
        - A configuration file (partition_finder.cfg)
        - A DNA alignment in Phylip format
    Take a look at the included 'example' folder for more details.

    The Output: A file in the same directory as the .cfg file, named
    'alignment_pf_output.txt' This file contains information on the best
    partitioning scheme, and the best model for each partiiton

    Usage Examples: 
        >python %prog example
        Analyse what is in the 'example' sub-folder in the current folder.

        >python %prog -v example
        Analyse what is in the 'example' sub-folder in the current folder, but
        show all the debug output

        >python %prog -c ~/data/frogs
        Check the configuration files in the folder data/frogs in the current
        user's home folder.

        >python %prog --force-restart ~/data/frogs
        Deletes any data produced by the previous runs (which is in
        ~/data/frogs/output) and starts afresh
    """
    parser = OptionParser(usage)
    parser.add_option(
        "-v", "--verbose",
        action="store_true", dest="verbose",
        help="show verbose (debug) output")
    parser.add_option(
        "-c", "--check-only",
        action="store_true", dest="check_only",
        help="just check the configuration files, don't do any processing")
    parser.add_option(
        "--force-restart",
        action="store_true", dest="force_restart",
        help="delete all previous output and start afresh (!)")
    parser.add_option(
        "-p", "--processes", 
        type="int", dest="processes", default=-1, metavar="N",
        help="Number of concurrent processes to use."
        " Use -1 to match the number of cpus on the machine."
        " The default is to use -1.")
    parser.add_option(
        "--show-python-exceptions",
        action="store_true", dest="show_python_exceptions",
        help="If errors occur, print the python exceptions")
    
    options, args = parser.parse_args()

    # We should have one argument: the folder to read the configuration from
    if not args:
        # Otherwise exit, printing the help
        parser.print_help()
        return 2

    # Load, using the first argument as the folder
    try:
        cfg = config.Configuration()
        cfg.load_base_path(args[0])

        #check for old analyses to see if we can use the old datas
        # config.check_for_old_config(cfg)
        
        if options.check_only:
            log.info("Exiting without processing (because of the -c/--check-only option ...")
        else:
            # Now try processing everything....
            anal = analysis.Analysis(
                cfg, 
                options.force_restart, 
                threads=options.processes,
            )
            anal.do_analysis()

        # Successful exit
        log.info("Processing complete.")
        return 0

    except util.PartitionFinderError:
        log.error("Failed to run. See previous errors.")
        if options.show_python_exceptions:
            raise

    except KeyboardInterrupt:
        log.error("User interrupted the Program")

    return 1


if __name__ == "__main__":
    # Well behaved unix programs exits with 0 on success...
    sys.exit(main())


