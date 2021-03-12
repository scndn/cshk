#!/usr/bin/env python

import sys
import os
import optparse
import MySQLdb
import zipfile
import struct

seis_roots = ['/home/scec-02/tera3d/CyberShake2007/data/PPFiles',
'/home/scec-04/tera3d/CyberShake/data/PPFiles',
'/home/scec-04/tera3d/CyberShake/data/from_scec-02/PPFiles']

def build_args():
	parser = optparse.OptionParser()
	parser.add_option("-r", "--run-id", dest="run", help="CyberShake Run ID", type="int", action='store')
	parser.add_option("-s", "--source-id", dest="source", help="Source ID", type="int", action='store')
	parser.add_option("-p", "--rupture-id", dest="rupture", help="Rupture ID", type="int", action='store')
	parser.add_option("-v", "--rup-var-id", dest="rupvar", help="Rupture Variation ID", type="int", action='store')
	parser.add_option("-o", "--output-file", dest="output", help="Output file name", type="string", action='store')
	parser.add_option("-i", "--include-header", help="Include header in output file.", action="store_true", default=False, dest="header")

	return parser


def get_site_name(run):
	conn = MySQLdb.connect(host="moment.usc.edu", db="CyberShake", user="cybershk_ro", passwd="CyberShake2007")
	cur = conn.cursor()
	query = "select S.CS_Short_Name from CyberShake_Sites S, CyberShake_Runs R where R.Site_ID=S.CS_Site_ID and R.Run_ID=%d" % (run)
	cur.execute(query)
	data = cur.fetchone()
	if data is None:
		#Try focal
		cur.close()
		conn.close()
	        conn = MySQLdb.connect(host="focal.usc.edu", db="CyberShake", user="cybershk_ro", passwd="CyberShake2007")
	        cur = conn.cursor()
		cur.execute(query)
		data = cur.fetchone()
	site_name = data[0]
	cur.close()
	return site_name


def find_rv(fp, rup_var_id, include_header):
	#zef = zipfile.open(target_clustered_file)
	#Read with header
	#version[8]
	#site_name[8]
	#padding[8]
	#source_id
	#rupture_id
	#rup_var_id
	#dt
	#nt
	#comps
	#det_max_freq
	#stoch_max_freq
	#Read into string buffer, so we can keep it if we need to keep the header
	header_string = fp.read(56)
	version_string = header_string[0:8]
	while version_string!="":
		version = "".join(struct.unpack('cccccccc', version_string))
		stopIndex = version.find('\0')
		site = "".join(struct.unpack('cccccccc', header_string[8:16]))
		stopIndex = site.find('\0')
		src = int(struct.unpack('i', header_string[24:28])[0])
		rup = int(struct.unpack('i', header_string[28:32])[0])
		rup_var = int(struct.unpack('i', header_string[32:36])[0])
		dt = float(struct.unpack('f', header_string[36:40])[0])
		nt = int(struct.unpack('i', header_string[40:44])[0])
		comps = int(struct.unpack('i', header_string[44:48])[0])
		det_max_freq = float(struct.unpack('f', header_string[48:52])[0])
		stoch_max_freq = float(struct.unpack('f', header_string[52:56])[0])
		data = fp.read(4*2*nt)
		if rup_var==rup_var_id:
			if include_header:
				return header_string + data
			else:
				return data
		header_string = fp.read(56)
		version_string = header_string[0:8]
	#if you make it here, didn't find the rupture variation
	return None


def find(site_name, run_id, source_id, rupture_id, rup_var_id, include_header):
	seis_dir = None
	for root in seis_roots:
		#Look for site_name/run_id
		test_path = os.path.join(root, site_name, str(run_id))
		if os.path.exists(test_path):
			seis_dir = test_path	
			break 
	if seis_dir is None:
		print "Could not find root dir for site %s, run_id %d, aborting." % (site_name, run_id)
		exit(1)
		#return None
	
	#Try to figure out what we're dealing with
	#Could be either zipped files or files at rupture level
	#See if a zipped file is present
	zipped_files = False
	test_file = "CyberShake_%s_%d_0_seismograms.zip" % (site_name, run_id)
	if os.path.exists(os.path.join(seis_dir, test_file)):
		zipped_files = True	
	
        #Could also be looking for a broadband file
	target_single_file = 'Seismogram_%s_%d_%d_%d.grm' % (site_name, source_id, rupture_id, rup_var_id)
	target_bb_clustered_file = 'Seismogram_%s_%d_%d_bb.grm' % (site_name, source_id, rupture_id)
        target_clustered_file = 'Seismogram_%s_%d_%d.grm' % (site_name, source_id, rupture_id)

	found = False

	if zipped_files:
		zipfilelist = os.listdir(seis_dir)
		for zip_file in zipfilelist:
			if zip_file.endswith("seismograms.zip"):
				zf = zipfile.ZipFile(os.path.join(seis_dir, zip_file))
				filelist = zf.namelist()
				for fullfile in filelist:
					#May have prepended path, like <src>/<rup>/<Seismogram>, so split on file
					file = fullfile.split('/')[-1]
					if file==target_single_file:
						print "Opening %s." % os.path.join(seis_dir, zip_file)
						zef = zf.open(fullfile)
						data = zef.read()
						zf.close()
						found = True
						break
					elif file==target_bb_clustered_file:
                                                print "Opening %s." % os.path.join(seis_dir, zip_file)
						zef = zf.open(fullfile)
                                                data = find_rv(zef, rup_var_id, include_header)
                                                if data is None:
                                                        print "Rupture variation %d could not be found in file %s." % (rup_var_id, target_clustered_file)
                                                        sys.exit(1)
                                                zf.close()
                                                found = True
                                                break
					elif file==target_clustered_file:
                                                print "Opening %s." % os.path.join(seis_dir, zip_file)
						#Need to find rupture variation in file
						zef = zf.open(fullfile)
						data = find_rv(zef, rup_var_id, include_header)
						if data is None:
							print "Rupture variation %d could not be found in file %s." % (rup_var_id, target_clustered_file)
							sys.exit(1)
						zf.close()
						found = True
						break
				if found:
					break
	else:
		filelist = os.listdir(seis_dir)
		for file in filelist:
			if file==target_single_file:
				fp = open(os.path.join(seis_dir, file), "rb")
				print "Opening %s." % (os.path.join(seis_dir, file))
				data = fp.read()
				fp.close()
				found = True
				break
			elif file==target_bb_clustered_file:
				fp = open(os.path.join(seis_dir, file), "rb")
                                print "Opening %s." % (os.path.join(seis_dir, file))
                                data = find_rv(fp, rup_var_id, include_header)
                                if data is None:
                                        print "Rupture variation %d could not be found in file %s." % (rup_var_id, target_clustered_file)
                                        sys.exit(2)
				fp.close()
                                found = True
                                break
			elif file==target_clustered_file:
				fp = open(os.path.join(seis_dir, file), "rb")
                                print "Opening %s." % (os.path.join(seis_dir, file))
				data = find_rv(fp, rup_var_id, include_header)
				if data is None:
					print "Rupture variation %d could not be found in file %s." % (rup_var_id, target_clustered_file)
					sys.exit(2)
				fp.close()
				found = True
				break
	if found:
		print "Seismogram found."
		return data
	print "Could not find %s, %s or %s in directory %s or in any zip files." % (target_single_file, target_bb_clustered_file, target_clustered_file, seis_dir)
	sys.exit(3)

def write_data(output_file, seis_data):
	#Write out string 
	fp = open(output_file, "wb")
	fp.write(seis_data)
	fp.flush()
	fp.close()


def main():
    
    print "...starting"
    
    f = open("events","r")

    try:
        
        for x in f:
            search_parameters = x.split()
            n_parameters = len(search_parameters)
            
            if n_parameters == 4:

                run_id = int(search_parameters[0])
                source_id = int(search_parameters[1])
                rupture_id = int(search_parameters[2])
                rup_var_id = int(search_parameters[3])
            
                if run_id==None or source_id==None or rupture_id==None or rup_var_id==None:
                    print "...missing id"
                    sys.exit(-1)

                output_file = None
                include_header = True
                site_name = get_site_name(run_id)

                output_file = "seis/Seismogram_%s_%d_%d_%d_%d.grm" % (site_name, run_id, source_id, rupture_id, rup_var_id)
                
                if os.path.exists(output_file):
                    print "...file exists"
                
                else:

                    try:
                        seis_data = find(site_name, run_id, source_id, rupture_id, rup_var_id, include_header)
                        write_data(output_file, seis_data)
                    except:
                        print "...could not find event"
            else:
                print "...incorrect number of parameters"
    
    except:
        print "...no input file"

    f.close()

if __name__=='__main__':
        main()
