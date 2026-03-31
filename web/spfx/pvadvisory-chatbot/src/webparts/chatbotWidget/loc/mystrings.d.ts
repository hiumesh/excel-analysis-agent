declare interface IChatbotWebPartStrings {
  PropertyPaneDescription: string;
  BasicGroupName: string;
  WidgetBaseUrlFieldLabel: string;
  AppLocalEnvironmentSharePoint: string;
  AppLocalEnvironmentTeams: string;
  AppLocalEnvironmentOffice: string;
  AppLocalEnvironmentOutlook: string;
  AppSharePointEnvironment: string;
  AppTeamsTabEnvironment: string;
  AppOfficeEnvironment: string;
  AppOutlookEnvironment: string;
  UnknownEnvironment: string;
}

declare module 'ChatbotWebPartStrings' {
  const strings: IChatbotWebPartStrings;
  export = strings;
}
