from lms.sqlite import LearningSearch


class CustomLearningSearch(LearningSearch):
	INDEXABLE_DOCTYPES = {
		**LearningSearch.INDEXABLE_DOCTYPES,
		"LMS Program": {
			"fields": [
				"name",
				"title",
				{"content": "title"},
				"published",
				"owner",
				{"modified": "creation"},
			],
		},
		"LMS Quiz": {
			"fields": [
				"name",
				"title",
				{"content": "title"},
				"owner",
				{"modified": "creation"},
			],
		},
		"LMS Assignment": {
			"fields": [
				"name",
				"title",
				{"content": "question"},
				"owner",
				{"modified": "creation"},
			],
		},
	}
 
    

	PROGRAM_FIELDS = [
		"name",
		"title",
		"description",
		"published",
		"creation",
		"modified",
		"owner",
	]

	QUIZ_FIELDS = [
		"name",
		"title",
		"creation",
		"modified",
		"owner",
	]

	ASSIGNMENT_FIELDS = [
		"name",
		"title",
		"question",
		"creation",
		"modified",
		"owner",
	]
 
	DOCTYPE_FIELDS = {
		**LearningSearch.DOCTYPE_FIELDS,
		"LMS Quiz": QUIZ_FIELDS,     
		"LMS Assignment": ASSIGNMENT_FIELDS,
	}


	
