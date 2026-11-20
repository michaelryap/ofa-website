/**
 * Adds an OFA > Publish to staging menu to the "OFA Website Copy" Google Doc.
 *
 * Publishing saves a snapshot of the doc to content/copy.json in the
 * ofa-website repo. That starts the "Build pages from Google Doc" GitHub
 * Action, which rebuilds the HTML pages and publishes them to GitHub Pages.
 *
 * Setup (once): see "Publish to staging" in the repo's CLAUDE.md.
 * This file is a copy for reference; the live version is in the doc's
 * Extensions > Apps Script editor.
 */

var OWNER = 'michaelryap';
var REPO = 'ofa-website';
var BRANCH = 'main';
var SNAPSHOT_PATH = 'content/copy.json';
var STAGING_URL = 'https://michaelryap.github.io/ofa-website/';

function onOpen() {
  DocumentApp.getUi()
    .createMenu('OFA')
    .addItem('Publish to staging', 'publishToStaging')
    .addToUi();
}

function publishToStaging() {
  var ui = DocumentApp.getUi();
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) {
    ui.alert('Publishing isn’t set up yet: the GitHub token is missing from Project Settings > Script Properties.');
    return;
  }

  // The doc as the Google Docs API sees it: headings, styles, lists, footnotes
  var doc = Docs.Documents.get(DocumentApp.getActiveDocument().getId());
  var snapshot = {
    documentId: doc.documentId,
    title: doc.title,
    revisionId: doc.revisionId,
    body: doc.body,
    footnotes: doc.footnotes || {},
    lists: doc.lists || {}
  };
  var json = JSON.stringify(snapshot, null, 1) + '\n';

  var api = 'https://api.github.com/repos/' + OWNER + '/' + REPO + '/contents/' + SNAPSHOT_PATH;
  var headers = {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };

  // GitHub needs the current file's id (sha) to replace it
  var current = UrlFetchApp.fetch(api + '?ref=' + BRANCH, { headers: headers, muteHttpExceptions: true });
  var sha = current.getResponseCode() === 200 ? JSON.parse(current.getContentText()).sha : undefined;

  var response = UrlFetchApp.fetch(api, {
    method: 'put',
    headers: headers,
    contentType: 'application/json',
    muteHttpExceptions: true,
    payload: JSON.stringify({
      message: 'Publish copy from Google Doc',
      content: Utilities.base64Encode(json, Utilities.Charset.UTF_8),
      branch: BRANCH,
      sha: sha
    })
  });

  var code = response.getResponseCode();
  if (code === 200 || code === 201) {
    ui.alert('Sent to staging',
      'The site will update in about two minutes:\n' + STAGING_URL +
      '\n\nProgress: https://github.com/' + OWNER + '/' + REPO + '/actions',
      ui.ButtonSet.OK);
  } else {
    ui.alert('Publishing failed (GitHub said ' + code + ')',
      response.getContentText().slice(0, 500), ui.ButtonSet.OK);
  }
}
