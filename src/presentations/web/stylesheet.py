stylesheet_css = """
/*****************************************************************************
* General Tag Styles
*****************************************************************************/
body {
margin: 0px;
padding: 0px;
color: black;
background-color: white;
font-size: 12px;
font-family: Verdana, Arial, Helvetica, sans-serif;
}
h1 {
font-size: 20px;
font-weight: bold;
}
h2 {
font-size: 16px;
font-weight: bold;
}
h3 {
font-size: 12px;
font-weight: normal;
font-style: normal;
}
h4 {
font-size: 12px;
font-weight: normal;
font-style: normal;
}
a:link {
color: #0033CC;
text-decoration: none;
}
a:visited {
color: #0033CC;
text-decoration: none;
}
a:hover {
color: #0033CC;
text-decoration: underline;
}
a:active {
color: #0033CC;
text-decoration: none;
}
a img {
border: 0px;
}
/*****************************************************************************
* General Page Header Style
*****************************************************************************/
#page-header {
padding: 0px;
margin-top: 10px;
margin-right: 10px;
}
/*****************************************************************************
* Page Logo Style
*****************************************************************************/
#page-header-logo {
float: left;
width: 200px;
height: 101px;
padding: 0px;
text-align: center;
vertical-align: middle;
}
/*****************************************************************************
* Page Title (Heading) Style
*****************************************************************************/
#page-header-title {
padding-top: 5px;
margin-left: 220px;
}
#page-header-title h1 {
text-align: left;
padding-bottom: 3px;
border-bottom: 2px solid #00008b;
}
/*****************************************************************************
* Header/Content Separator Style
*****************************************************************************/
#page-header-separator {
clear: both;
}
/*****************************************************************************
* Navigation Menu Style
*****************************************************************************/
#page-navigation-menu {
width: 200px;
padding-left: 10px;
padding-top: 30px;
}
#page-navigation-menu ul {
margin: 0px;
padding: 0px;
list-style-type: none;
}
#page-navigation-menu li {
margin: 0px;
margin-top: 1px;
margin-bottom: 1px;
padding: 1px 0px 1px 3px;
}
#page-navigation-menu a {
display: block;
}
#page-navigation-menu li:hover {
background-color: #c5d6fc;
}
#page-navigation-menu li.selected {
background-color: #c5d6fc;
}
#page-navigation-menu ul li {
margin-bottom: 10px;
}
#page-navigation-menu ul li.submenu {
font-weight: bold;
}
#page-navigation-menu ul li.submenu:hover {
background-color: #ffffff;
}
#page-navigation-menu ul li.submenu ul {
margin-left: 10px;
}
#page-navigation-menu ul li.submenu ul li {
margin-bottom: 0px;
font-weight: normal;
}
/*****************************************************************************
* General Page Content Style
*****************************************************************************/
#page-content {
margin-top: 0px;
margin-left: 0px;
margin-right: 10px;
margin-bottom: 20px;
}
/*****************************************************************************
* General Page Content Status Style (non-menu based page)
*****************************************************************************/
#page-status-content {
margin-top: 10px;
margin-left: 100px;
margin-right: 100px;
margin-bottom: 20px;
}
/*****************************************************************************
* Page Messages Style
*****************************************************************************/
#page-content-messages {
margin-left: 100px;
margin-right: 100px;
}
#page-content-messages div.status-message {
padding: 5px;
color: #00008B;
display: block;
font-size: 12px;
text-align: center;
border-width: thin;
border-style: solid;
border-color: #00008B;
background-color: #E8E8E8;
}
#page-content-messages div.error-message {
padding: 5px;
color: #E80000;
font-size: 12px;
font-weight: bold;
text-align: center;
border-width: thin;
border-style: solid;
border-color: #E80000;
background-color: #FFDDDD;
}
/*****************************************************************************
* Page Help Bar Style
*****************************************************************************/
#page-content-help {
height: 20px;
padding-top: 5px;
padding-bottom: 5px;
text-align: right;
vertical-align: middle;
}
#page-content-help img {
padding-right: 5px;
vertical-align: middle;
}
/*****************************************************************************
* General Page Content Body Style
*****************************************************************************/
#page-content-body {
border: 1px solid #00008b;
}
#page-content-body div.page-heading {
color: white;
padding: 4px 5px 4px 5px;
background-color: #00008b;
}
#page-content-body td.page-heading-cell {
color: white;
width: 99%;
white-space: nowrap;
vertical-align: middle;
background-color: #00008b;
}
#page-content-body div.page-heading h2 {
margin: 0px;
padding: 0px;
vertical-align: middle;
}
#page-content-body div.page-heading a {
color: white;
vertical-align: middle;
}
#page-content-body td.page-subheading-cell {
color: white;
width: 1%;
white-space: nowrap;
text-align: right;
vertical-align: middle;
background-color: #00008b;
}
#page-content-body td.page-subheading-cell a {
color: white;
vertical-align: middle;
}
#page-content-body td.page-subheading-cell span {
vertical-align: middle;
}
#page-content-body td.page-subheading-cell img {
vertical-align: middle;
}
#page-content-body div.page-htmlcontent {
margin: 5px;
}
/*****************************************************************************
* General Tab Content Body Style
*****************************************************************************/
#page-content-body div.tab-heading {
}
#page-content-body div.tab-content {
margin-bottom: 5px;
}
#page-content-body div.tab-content div.tab-content-heading {
margin: 0px;
color: #00008b;
background-color: #c5d6fc;
padding: 3px 5px 3px 5px;
}
#page-content-body div.tab-content div.tab-content-heading h3 {
margin: 0px;
padding: 0px;
margin-left: 15px;
}
#page-content-body div.tab-content div.tab-content-heading h3 a {
display: block;
}
#page-content-body div.tab-content div.tab-content-heading h3.tab-selected {
font-weight: bold;
}
#page-content-body div.tab-content div.tab-content-heading img {
padding-top: 3px;
float: left;
}
#page-content-body div.tab-content div.tab-content-body {
margin: 10px;
}
#page-content-body div.tab-content div.tab-content-body-heading {
padding-bottom: 10px;
}
/*****************************************************************************
* General Page Content Table & List Styles
*****************************************************************************/
#page-content-body table.page-content-table {
width: 98%;
}
#page-content-body table.page-content-table th {
white-space: nowrap;
padding: 3px 10px 3px 10px;
}
#page-content-body table.page-content-table td {
white-space: nowrap;
padding: 3px 10px 3px 10px;
}
#page-content-body table.page-content-table thead tr th {
border-bottom: 1px solid #00008b;
}
#page-content-body table.page-content-table .column-header {
width: 1%;
}
#page-content-body table.page-content-table .column-spacing {
width: 100%;
}
#page-content-body table.page-content-table .primary-row {
background-color: white;
}
#page-content-body table.page-content-table .secondary-row {
background-color: #dcdcdc;
}
/*****************************************************************************
* General Page Content Listbox Styles
*****************************************************************************/
#page-content-body table.page-content-listbox {
border: 1px solid #00008b;
}
#page-content-body table.page-content-listbox th {
white-space: nowrap;
padding: 3px 10px 3px 10px;
}
#page-content-body table.page-content-listbox td {
white-space: nowrap;
padding: 3px 10px 3px 10px;
}
#page-content-body table.page-content-listbox thead tr th {
color: white;
background-color: #00008b;
}
#page-content-body table.page-content-listbox .primary-row {
background-color: white;
}
#page-content-body table.page-content-listbox .secondary-row {
background-color: white;
}
#page-content-body table.page-content-listbox .field-entry-row {
background-color: #c5d6fc;
}
/*****************************************************************************
* General Page Content Listbox Styles (w/ Heading)
*****************************************************************************/
#page-content-body table.page-content-listbox2 {
border: 1px solid #00008b;
}
#page-content-body table.page-content-listbox2 th {
white-space: nowrap;
padding: 3px 10px 3px 10px;
}
#page-content-body table.page-content-listbox2 td {
white-space: nowrap;
padding: 3px 10px 3px 10px;
}
#page-content-body table.page-content-listbox2 thead tr th {
color: black;
background-color: #c3c3c3;
}
#page-content-body table.page-content-listbox2 .listbox-heading {
font-weight: bold;
color: white;
background-color: #00008b;
}
#page-content-body table.page-content-listbox2 .primary-row {
background-color: white;
}
#page-content-body table.page-content-listbox2 .secondary-row {
background-color: white;
}
#page-content-body table.page-content-listbox2 .field-entry-row {
background-color: #c5d6fc;
}
/*****************************************************************************
* Page and Form Field & Input Styles
*****************************************************************************/
#page-content .field-input {
width: 99%;
white-space: nowrap;
text-align: left;
}
#page-content .field-input-small {
width: 1%;
white-space: nowrap;
text-align: left;
}
#page-content .field-checkbox {
width: 99%;
white-space: nowrap;
text-align: left;
}
#page-content .field-checkbox-small {
width: 1%;
white-space: nowrap;
text-align: left;
}
#page-content .field-label {
width: 1%;
white-space: nowrap;
text-align: right;
}
#page-content .field-label-left {
width: 1%;
white-space: nowrap;
text-align: left;
}
#page-content .field-value {
width: 99%;
white-space: nowrap;
text-align: left;
}
#page-content .field-value-small {
width: 1%;
white-space: nowrap;
text-align: left;
}
#page-content .field-spacing {
padding-left: 10px;
}
#page-content .field-expansion {
width: 99%;
}
#page-content .field-indent {
padding-left: 30px;
}
#page-content .field-error {
border-style: solid;
border-color: #E80000;
background-color: #FFDDDD;
}
#page-content .field-warning {
border-style: solid;
border-color: #E8E800;
background-color: #FFFFC0;
}
/*****************************************************************************
* Miscellaneous Page Content Styles
*****************************************************************************/
#page-content-body .page-separator {
color: #00008b;
margin: 0px 0px 5px 0px;
padding: 3px 5px 3px 5px;
background-color: #c5d6fc;
}
#page-content-body .page-section {
padding: 5px;
}
#page-content-body .permission-select {
width: 11em;
}
#page-content-body .permission-label {
width: 25%;
white-space: nowrap;
text-align: right;
}
#page-content-body .permission-select {
width: 11em;
}
#page-content-body .stats-label {
width: 25%;
white-space: nowrap;
text-align: right;
}
/*****************************************************************************
* Form Style
*****************************************************************************/
form.form-content {
margin: 0px;
padding: 0px;
}
/*****************************************************************************
* Form Button Bar Style
*****************************************************************************/
form.form-content div.form-buttons {
margin-top: 10px;
padding-top: 5px;
padding-bottom: 5px;
border-top: 1px solid #00008b;
}
/*****************************************************************************
* Footer/Content Separator Style
*****************************************************************************/
#page-footer-separator {
clear: both;
}
/*****************************************************************************
* Copyright Style
*****************************************************************************/
#page-footer-copyright {
margin-top: 10px;
margin-bottom: 10px;
text-align: center;
font-size: 10px;
}
/*****************************************************************************
* General Help Page Header Style
*****************************************************************************/
#help-page-header {
padding: 0px;
margin-top: 10px;
margin-right: 10px;
}
/*****************************************************************************
* Help Page Logo Style
*****************************************************************************/
#help-page-header-logo {
float: left;
width: 200px;
height: 101px;
padding: 0px;
text-align: center;
vertical-align: middle;
}
/*****************************************************************************
* Help Page Title (Heading) Style
*****************************************************************************/
#help-page-header-title {
padding-top: 5px;
margin-left: 220px;
}
#help-page-header-title h1 {
text-align: left;
padding-bottom: 3px;
}
/*****************************************************************************
* Help Header/Content Separator Style
*****************************************************************************/
#help-page-header-separator {
clear: both;
}
/*****************************************************************************
* General Help Page Sub-Header Style
*****************************************************************************/
#help-page-subheader {
height: 30px;
margin-left: 10px;
margin-right: 10px;
margin-top: 30px;
margin-bottom: 30px;
border-bottom: 1px solid #00008b;
}
/*****************************************************************************
* Current Help Page Title Style
*****************************************************************************/
#help-page-subheader-title {
float: left;
padding: 0px;
text-align: left;
vertical-align: middle;
}
#help-page-subheader-title h2 {
font-size: 18px;
font-weight: bold;
margin: 0px;
padding: 0px;
vertical-align: middle;
}
/*****************************************************************************
* Help Navigation Buttons Style
*****************************************************************************/
#help-page-subheader-navigation {
text-align: right;
vertical-align: middle;
}
#help-page-subheader-navigation a {
vertical-align: middle;
}
#help-page-subheader-navigation img {
border: 0px;
vertical-align: middle;
}
/*****************************************************************************
* Help Table of Contents Style
*****************************************************************************/
#help-page-content-toc {
padding: 10px;
}
#help-page-content-toc ul {
margin: 0px;
padding: 0px;
list-style-type: none;
}
#help-page-content-toc li {
margin: 0px;
padding: 0px;
list-style-type: none;
}
#help-page-content-toc ul li {
margin-bottom: 10px;
}
#help-page-content-toc ul li.section {
font-weight: bold;
}
#help-page-content-toc ul li.section a {
font-weight: normal;
}
#help-page-content-toc ul li.section ul {
margin-left: 20px;
}
#help-page-content-toc ul li.section ul li {
margin-bottom: 0px;
font-weight: normal;
}
/*****************************************************************************
* General Help Page Content & Body Style
*****************************************************************************/
#help-page-content {
margin: 10px;
}
#help-page-content-body {
font-size: 12px;
}
#help-page-content .field-spacing {
padding-left: 10px;
}
#help-page-content .field-indent {
padding-left: 30px;
}
#help-page-content-body p {}
#help-page-content-body div.help-section {
margin-left: 5px;
}
#help-page-content-body div.help-section h3 {
font-size: 14px;
font-weight: bold;
margin-left: -5px;
text-decoration: underline;
}
#help-page-content-body div.help-section p {
font-size: 12px;
}
#help-page-content-body div.help-field {}
#help-page-content-body div.help-field h4 {
font-size: 12px;
font-weight: bold;
margin-top: 0px;
padding-top: 0px;
margin-bottom: 2px;
padding-bottom: 0px;
}
#help-page-content-body div.help-field p {
font-size: 12px;
margin-top: 0px;
padding-top: 0px;
}
/*****************************************************************************
* General Help Page Content & Body Style
*****************************************************************************/
#help-page-content-body table.help-content-table {
border-top: 1px solid black;
border-left: 1px solid black;
}
#help-page-content-body table.help-content-table thead {
background-color: #c3c3c3
}
#help-page-content-body table.help-content-table thead tr th {
padding: 3px;
font-weight: bold;
text-align: center;
vertical-align: middle;
border-right: 1px solid black;
border-bottom: 1px solid black;
}
#help-page-content-body table.help-content-table tbody tr td {
padding: 2px;
text-align: left;
vertical-align: top;
border-right: 1px solid black;
border-bottom: 1px solid black;
}
/*****************************************************************************
* Help Header/Content Separator Style
*****************************************************************************/
#help-page-footer-separator {
clear: both;
}
/*****************************************************************************
* Help Page Footer & Copyright Style
*****************************************************************************/
#help-page-footer-copyright {
font-size: 10px;
padding-top: 15px;
text-align: center;
vertical-align: bottom;
}
/*****************************************************************************
* Main Web UI Wizard Styles
*****************************************************************************/
#wizard {
margin: 0px;
padding: 0px;
}
/*****************************************************************************
* Web UI Wizard Header (Title and Description bar)
*****************************************************************************/
#wizard-header-bar {
height: 60px;
color: white;
background-color: navy;
padding: 5px;
border-bottom: 2px solid #C0C0FF;
}
#wizard-header-bar h3 {
font-size: 115%;
margin-top: 0px;
padding-top: 0px;
margin-bottom: 0px;
padding-bottom: 3px;
font-style: normal;
font-weight: bold;
color: white;
background-color: navy;
}
#wizard-header-bar p {
font-size: 90%;
margin-top: 0px;
padding-top: 0px;
margin-left: 10px;
color: white;
background-color: navy;
}
/*****************************************************************************
* Web UI Wizard Content Body
*****************************************************************************/
#wizard-page-body {
height: 260px;
padding: 5px;
padding-top: 10px;
overflow: auto;
}
#wizard-page-content {
}
/*****************************************************************************
* Web UI Wizard Messages Style
*****************************************************************************/
#wizard-page-messages {
margin-left: 100px;
margin-right: 100px;
}
#wizard-page-messages div.status-message {
padding: 5px;
color: #00008B;
display: block;
font-size: 12px;
text-align: center;
border-width: thin;
border-style: solid;
border-color: #00008B;
background-color: #E8E8E8;
}
#wizard-page-messages div.error-message {
padding: 5px;
color: #E80000;
font-size: 12px;
font-weight: bold;
text-align: center;
border-width: thin;
border-style: solid;
border-color: #E80000;
background-color: #FFDDDD;
}
/*****************************************************************************
* Web UI Wizard Button Bar (Submit Buttons)
*****************************************************************************/
#wizard-button-bar {
height: 30px;
margin: 0px;
padding-left: 5px;
padding-right: 5px;
border-top: 2px solid #C0C0FF;
}
#wizard-button-bar table {
width: 99%;
}
#wizard-button-bar table td.help-button-cell {
text-align: left;
}
#wizard-button-bar table td.navigation-button-cell {
text-align: right;
}
"""

