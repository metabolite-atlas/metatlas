workflow metatlas_wf {
    Int threads
    File config
    File tree_lookup
    File api_file

    #
    # convert raw_to_mzml
    #
    call find_task_files as files_for_mzml_alias {
         input: conversion_task = "raw_to_mzml",
                api_file = api_file
    }
    
	if (files_for_mzml_alias.should_continue) {
	  scatter (paths in files_for_mzml_alias.file_pairs) {
		call raw_to_mzml {
           input: paths=paths
		}
	  }
    }

    #
    # convert mzml_to_hdf5
    #
    call find_task_files as files_for_hdf5_alias {
      input: conversion_task = "mzml_to_hdf5",
            api_file = api_file
    }

	if (files_for_hdf5_alias.should_continue) {
	  scatter (paths in files_for_hdf5_alias.file_pairs) {
		call mzml_to_hdf5 {
          input: paths=paths
		}
	  }
    }

#        #
#        # convert mzml_to_pactolus
#        #
#        call find_task_files as files_for_pactolus_alias {
#          input: conversion_task = "mzml_to_pactolus",
#               api_file = api_file
#        }
#    
#        scatter (paths in files_for_pactolus_alias.file_pairs) {
#          call mzml_to_pactolus {
#              input: paths=paths,
#                     config = config,
#                     tree_lookup = tree_lookup,
#                     threads = threads
#          }
#        }
#
#    #
#    # convert mzml_to_spectralhits
#    #
#    call find_task_files as files_for_spectralhits_alias {
#      input: conversion_task = "mzml_to_spectralhits",
#            api_file = api_file
#    }
#
#    scatter (paths in files_for_spectralhits_alias.file_pairs) {
#      call mzml_to_spectralhits {
#          input: paths=paths,
#                 config = config
#      }
#    }
}


### ------------------------------------------ ###

task find_task_files {
    # This task gets files from LIMS that are in need of processing (i.e. mzml_to_hdf5).  
    # If a sample only has a raw file, it will be added to the raw_to_mzml list.
    # Samples must already have a mzml file to be added to the mzml_to_hdf5, 
    # mzml_to_pactolus, or mzml_to_spectralhits lists.
    # This script outputs a table where each row is a input file path and an output filepath.
    # The output filepath is a suggestion of where the result should be copied but can be overwitten.

    String conversion_task
    File api_file

    command <<<
        SECONDS=0

		touch raw_files.tsv

        #shifter --image=jfroula/jaws-pactolus-spectral:1.2.0 \
        #files_per_task.py --task ${conversion_task} --out raw_files.tsv

        #source /global/cscratch1/sd/jfroula/JAWS/jgi-wdl-catalog/jaws-benbowen/labkey-env/bin/activate && \
        shifter --image=jfroula/jaws-pactolus-spectral:1.2.0 \
        /global/cscratch1/sd/jfroula/JAWS/jgi-wdl-catalog/jaws-benbowen/scripts/files_per_task.py --task ${conversion_task} --out raw_files.tsv  --api ${api_file}
        #&& deactivate

        if [[ -s "raw_files.tsv" ]]; then
			echo true > continue
		else
            echo "no raw files to process."
			echo false > continue
        fi  

        # get time this task took
        hrs=$(( SECONDS/3600 )); mins=$(( (SECONDS-hrs*3600)/60)); secs=$(( SECONDS-hrs*3600-mins*60 ))
        #printf 'Time spent: %02d:%02d:%02d\n' $hrs $mins $secs
    >>>

#   runtime {
#     docker: jfroula/jaws-pactolus-spectral:1.2.0
#     nodes: 1
#     time: "08:00:00"
#   }

    output {
        Array[Array[String]?] file_pairs = read_tsv("raw_files.tsv")
		Boolean should_continue = read_boolean("continue")
    }
}


task raw_to_mzml {

    Array[String] paths

    command <<<
        SECONDS=0
        key=${paths[0]}
        input_path=${paths[1]}
        output_path=${paths[2]}
        required_mzml_size=1000000 # 1Mb

		echo "### creating mzml"

        shifter --volume=$(pwd):/mywineprefix --image=biocontainers/pwiz:phenomenal-v3.0.18205_cv1.2.54 mywine msconvert --32 --mzML $input_path
        mzml_file=$(ls *.mzML)

        if [[ ! -s $mzml_file ]]; then
            >&2 echo "Warning: no mzml file was created."
            exit 0
        fi

        # run a little file size test to make sure the newly created mzml file is at least 1Mb.
        my_mzml=$(ls *.mzML)
        size=$(ls -l $my_mzml | awk '{print $5}')
        warning=
        if [[ $size -lt $required_mzml_size ]]; then
          warning="warning: file $my_mzml is less than $required_mzml_size."
        fi

        # write output path to file so we can copy the resulting
        # file from this task to the proper destination after jaws is completed.
        #echo $key $output_path $size $warning > outpath

        # Write some metadata about the conversion process to a file for parsing downstream.
        # Info from this table will be used to update LIMS.
        cat <<EOF > meta.json
        {
          key: $key
          outpath: $output_path
          filesize: $size
          warning: $warning
        }
        EOF

        # get time this task took
        hrs=$(( SECONDS/3600 )); mins=$(( (SECONDS-hrs*3600)/60)); secs=$(( SECONDS-hrs*3600-mins*60 ))
        printf 'Time spent: %02d:%02d:%02d\n' $hrs $mins $secs
    >>> 

    runtime {
        time: "01:00:00"
        mem: "5G"
        poolname: "metatlas"
        node: 1
        nwpn: 8
    }

    output {
	  Array[File]? mzml_files = glob("*.mzML")
    }
}

task mzml_to_hdf5 {
    Array[String] paths
    String dollar='$'

    command <<<
        SECONDS=0
        key=${paths[0]}
        input_path=${paths[1]}
        output_path=${paths[2]}
        bname=$(basename $input_path)
        filename="${dollar}{bname%.*}"
        required_h5_size=1000000  # 1Mb

        shifter --image=jfroula/jaws-pactolus-spectral:1.2.0 mzml_loader_jaws.py \
        -i $input_path \
        -o $filename.h5

        if [[ -s "$filename.h5" ]]; then
            # validate that h5 file is greater than 5M
            filesize=$(stat --printf="%s" $filename.h5)
            if [[ $filesize -lt 5000000 ]]; then
              echo "File size for $filename.h5 is less than the minimum 5Mb size."
            fi
        else
            echo "Warning: h5 file missing or empty."
        fi  


        # run a little file size test to make sure the newly created mzml file is at least 1Mb.
        my_h5=$(ls *.h5)
        size=$(ls -l $my_h5 | awk '{print $5}')
        warning=
        if [[ $size -lt $required_h5_size ]]; then
           warning="warning: file $my_h5 is less than $required_h5_size."
        fi

        # write output path to file so we can copy the resulting 
        # file from this task to the proper destination after jaws is completed.
        #echo $key $output_path $size $warning> outpath

		# Write some metadata about the conversion process to a file for parsing downstream.
        # Info from this table will be used to update LIMS.
        cat <<EOF > meta.json
        {
          key: $key
          outpath: $output_path
          filesize: $size
          warning: $warning
        }
		EOF

        # get time this task took
        hrs=$(( SECONDS/3600 )); mins=$(( (SECONDS-hrs*3600)/60)); secs=$(( SECONDS-hrs*3600-mins*60 ))
        printf 'Time spent: %02d:%02d:%02d\n' $hrs $mins $secs
    >>> 

    runtime {
        time: "01:00:00"
        mem: "5G"
        poolname: "metatlas"
        node: 1
        nwpn: 8
    }

    output {
      Array[File]? h5 = glob("*.h5")
    }
}

task mzml_to_pactolus {
    Array[String] paths
    File config
    File tree_lookup
    Int threads

    command <<<
        SECONDS=0
        key=${paths[0]}
        input_path=${paths[1]}
        output_path=${paths[2]}

        echo -e "\n\n### creating pactolus"
        shifter --image=jfroula/jaws-pactolus-spectral:1.2.0 python /root/pactolus/pactolus/score_mzmlfile.py \
        --infile $input_path \
        --ms2_tolerance 0.0100 \
        --ms1_tolerance 0.0100 \
        --ms1_pos_neutralizations 1.007276 18.033823 22.989218 \
        --ms2_pos_neutralizations -1.00727646677 -2.01510150677 0.00054857990946 \
        --ms1_neg_neutralizations -1.007276 59.013851 \
        --ms2_neg_neutralizations 1.00727646677 2.01510150677 -0.00054857990946 \
        --tree_file ${tree_lookup} \
        --num_cores ${threads}

        if [[ ! "$lcms_filename.pactolus.gz" ]]; then
            >&2 echo "Warning: no pactolus file created."
        fi

        # write output path to file so we can copy the resulting 
        # file from this task to the proper destination after jaws is completed.
        #echo $key $output_path > outpath

		# Write some metadata about the conversion process to a file for parsing downstream.
        # Info from this table will be used to update LIMS.
        cat <<EOF > meta.json
        {
          key: $key
          outpath: $output_path
        }
		EOF

        # get time this task took
        hrs=$(( SECONDS/3600 )); mins=$(( (SECONDS-hrs*3600)/60)); secs=$(( SECONDS-hrs*3600-mins*60 ))
        printf 'Time spent: %02d:%02d:%02d\n' $hrs $mins $secs
    >>>

    runtime {
        time: "01:00:00"
        mem: "5G"
        poolname: "metatlas"
        node: 1
        nwpn: 8
    }

    output {
      Array[File]? pactolus = glob("*.pactolus.gz")
    }
}

task mzml_to_spectralhits {
    Array[String] paths
    File config

    command <<<
        SECONDS=0
        key=${paths[0]}
        input_path=${paths[1]}
        output_path=${paths[2]}

        # creates spectral-hits.tab.gz from spectral_hits_cmd
        shifter --image=jfroula/jaws-pactolus-spectral:1.2.0 \
        /usr/local/bin/spectral_hits_jaws.py -f -m $input_path -l "myfile_spectral-hits.tab.gz" -c ${config} 2> myerr.log
        if [[ -s "myerr.log" ]]; then
          >&2 cat myerr.log
        fi

        if [[ ! "myfile_spectral-hits.tab.gz" ]]; then
            >&2 echo "Warning: no spectralhits file created."
        fi

        # write output path to file so we can copy the resulting 
        # file from this task to the proper destination after jaws is completed.
        #echo $key $output_path > outpath

		# Write some metadata about the conversion process to a file for parsing downstream.
        # Info from this table will be used to update LIMS.
        cat <<EOF > meta.json
        {
          key: $key
          outpath: $output_path
          filesize: $size
          warning: $warning
        }
		EOF

        # get time this task took
        hrs=$(( SECONDS/3600 )); mins=$(( (SECONDS-hrs*3600)/60)); secs=$(( SECONDS-hrs*3600-mins*60 ))
        printf 'Time spent: %02d:%02d:%02d\n' $hrs $mins $secs
    >>> 

    runtime {
        time: "01:00:00"
        mem: "5G"
        poolname: "metatlas"
        node: 1
        nwpn: 8
    }

    output {
      Array[File]? spectralhits =  glob("*_spectral-hits.tab.gz")
    }
}

