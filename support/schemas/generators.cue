package problemformat

// To validate generators.yaml using cue:
// > cue vet generators.yaml *.cue -d "#Generators"

import "struct"

#command: !="" & (=~"^[^{}]*(\\{(name|seed(:[0-9]+)?)\\}[^{}]*)*$")
#file_config: {
	solution?:    #command | null // null disallowed (specify #testcase.ans instead)
	visualizer?:  #command | null // null means: skip visualisation
	random_salt?: string
}

#testcase: #command |      // same as command: #command
	null |                 // same as path: null
	{
		command?: #command // invocation of a generator
		path?:    #path |  // copy generators/path.{ext} to path/to/testcase{.ext} 
			null           // leave path/to/testcase{.ext} alone
		in?:   string      // explicitly given contents for .in
		ans?:  string
		desc?: string
		hint?: string
		#file_config
	} 

#data_dict: [string]: #testgroup | #testcase

#testgroup: {
	#file_config
	"testdata.yaml"?: #testdata_settings                                   // TODO should this field be testdata_settings or settings?
	data:             #data_dict | [...{#data_dict & struct.MaxFields(1)}] // list of singleton dicts
}

#Generators: {
	generators?: [string]: [...string]
	#testgroup
	... // Do allow unknown_key at top level for tooling
} & 
	{ data: close({
		// Restrict top level data to testgroups 'sample', 'secret'
		sample: #testgroup
		secret: #testgroup
	})
}
