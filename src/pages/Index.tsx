import Header from "@/components/Header";
import conferencesData, { conferencesByTitle } from "@/utils/conferenceLoader";
import { Conference } from "@/types/conference";
import { useState, useMemo, useEffect } from "react";
import { Switch } from "@/components/ui/switch"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { X, Globe, HelpCircle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { getAllCountries } from "@/utils/countryExtractor";
import { hasUpcomingDeadlines, getAllDeadlines, getDaysRemaining } from "@/utils/deadlineUtils";
import { getDeadlineInLocalTime } from "@/utils/dateUtils";
import ConferenceTable, { type SortMode, type TableRow } from "@/components/ConferenceTable";
import { AcceptedPapersStatusProvider } from "@/hooks/useAcceptedPapersStatus";

const Index = () => {
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());
  const [selectedCountries, setSelectedCountries] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [showPastConferences, setShowPastConferences] = useState(false);
  const [showTopTierOnly, setShowTopTierOnly] = useState(true);
  const [sortMode, setSortMode] = useState<SortMode>("deadline");

  const categoryButtons = useMemo(() => {
    if (!Array.isArray(conferencesData)) return [];

    const relevantConferences = conferencesData.filter((conf: Conference) => {
      if (!showPastConferences && !hasUpcomingDeadlines(conf)) return false;
      if (showTopTierOnly && conf.era_rating !== 'a') return false;
      return true;
    });

    // Only show these primary tags as filter buttons
    const primaryTags: { id: string; label: string }[] = [
      { id: "machine-learning", label: "Machine Learning" },
      { id: "natural-language-processing", label: "NLP" },
      { id: "recommender-systems", label: "Recommender Systems" },
      { id: "computer-vision", label: "Computer Vision" },
      { id: "data-mining", label: "Data Mining" },
      { id: "information-retrieval", label: "Information Retrieval" },
      { id: "human-computer-interaction", label: "HCI" },
      { id: "large-language-models", label: "LLM" },
      { id: "web-search", label: "Web Search" },
      { id: "speech", label: "Speech" },
      { id: "robotics", label: "Robotics" },
      { id: "computer-graphics", label: "Computer Graphics" },
    ];

    const tagCounts = new Map<string, number>();
    relevantConferences.forEach((conf: Conference) => {
      if (Array.isArray(conf.tags)) {
        conf.tags.forEach(tag => {
          tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
        });
      }
    });

    return primaryTags.filter(t => tagCounts.has(t.id));
  }, [showPastConferences, showTopTierOnly]);

  // Filter determines which conference TITLES to show
  const matchedTitles = useMemo(() => {
    if (!Array.isArray(conferencesData)) return new Set<string>();

    const titles = new Set<string>();
    conferencesData.forEach((conf: Conference) => {
      if (!showPastConferences && !hasUpcomingDeadlines(conf)) return;
      if (showTopTierOnly && conf.era_rating !== 'a') return;

      const matchesTags = selectedTags.size === 0 ||
        (Array.isArray(conf.tags) && conf.tags.some(tag => selectedTags.has(tag)));
      const matchesCountry = selectedCountries.size === 0 ||
        (conf.country && selectedCountries.has(conf.country));
      const matchesSearch = searchQuery === "" ||
        conf.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (conf.full_name && conf.full_name.toLowerCase().includes(searchQuery.toLowerCase()));

      if (matchesTags && matchesCountry && matchesSearch) {
        titles.add(conf.title);
      }
    });
    return titles;
  }, [selectedTags, selectedCountries, searchQuery, showPastConferences, showTopTierOnly]);

  // Build table rows with ALL years for matched titles
  const { tableRows, yearColumns } = useMemo(() => {
    const rows: TableRow[] = [];
    const yearsSet = new Set<number>();

    for (const title of matchedTitles) {
      const allYears = conferencesByTitle.get(title);
      if (!allYears || allYears.length === 0) continue;

      const latest = allYears[0]; // most recent year (sorted desc in conferenceLoader)
      const confs = new Map<number, Conference>();
      allYears.forEach((c) => {
        confs.set(c.year, c);
        yearsSet.add(c.year);
      });

      rows.push({
        title: latest.title,
        fullName: latest.full_name,
        eraRating: latest.era_rating,
        rankings: latest.rankings,
        tags: Array.isArray(latest.tags) ? latest.tags : [],
        conferences: confs,
      });
    }

    const yearColumns = Array.from(yearsSet).sort((a, b) => b - a);

    // Helper: get abstract/paper deadline date for sorting
    const getAbstractDeadlineTime = (row: TableRow): number => {
      let earliest = Infinity;
      for (const conf of row.conferences.values()) {
        const all = getAllDeadlines(conf);
        const dl = all.find(d => d.type === "abstract") ||
                   all.find(d => d.type === "paper" || d.type === "submission") ||
                   all[0];
        if (dl) {
          const days = getDaysRemaining(dl, conf.timezone);
          // Only consider upcoming (days > 0)
          if (days !== null && days > 0) {
            const date = getDeadlineInLocalTime(dl.date, dl.timezone || conf.timezone);
            if (date) earliest = Math.min(earliest, date.getTime());
          }
        }
      }
      return earliest;
    };

    if (sortMode === "name") {
      rows.sort((a, b) => a.title.localeCompare(b.title));
    } else {
      // Upcoming (has future abstract deadline) first, then closed at bottom
      rows.sort((a, b) => {
        const aTime = getAbstractDeadlineTime(a);
        const bTime = getAbstractDeadlineTime(b);
        // Both have upcoming → sort by earliest
        // One has upcoming, other doesn't → upcoming first
        // Neither has upcoming → keep original order
        if (aTime === Infinity && bTime === Infinity) return 0;
        if (aTime === Infinity) return 1;
        if (bTime === Infinity) return -1;
        return aTime - bTime;
      });
    }

    return { tableRows: rows, yearColumns };
  }, [matchedTitles, sortMode]);

  const handleTagsChange = (newTags: Set<string>) => {
    setSelectedTags(newTags);
    const searchParams = new URLSearchParams(window.location.search);
    if (newTags.size > 0) {
      searchParams.set('tags', Array.from(newTags).join(','));
    } else {
      searchParams.delete('tags');
    }
    window.history.replaceState({}, '', `${window.location.pathname}?${searchParams}`);
  };

  const handleCountriesChange = (newCountries: Set<string>) => {
    setSelectedCountries(newCountries);
    const searchParams = new URLSearchParams(window.location.search);
    if (newCountries.size > 0) {
      searchParams.set('countries', Array.from(newCountries).join(','));
    } else {
      searchParams.delete('countries');
    }
    window.history.replaceState({}, '', `${window.location.pathname}?${searchParams}`);
  };

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const tagsParam = searchParams.get('tags');
    const countriesParam = searchParams.get('countries');
    if (tagsParam) setSelectedTags(new Set(tagsParam.split(',')));
    if (countriesParam) setSelectedCountries(new Set(countriesParam.split(',')));
  }, []);

  useEffect(() => {
    const handleUrlChange = () => {
      const searchParams = new URLSearchParams(window.location.search);
      const tagsParam = searchParams.get('tags');
      const countriesParam = searchParams.get('countries');
      setSelectedTags(tagsParam ? new Set(tagsParam.split(',')) : new Set());
      setSelectedCountries(countriesParam ? new Set(countriesParam.split(',')) : new Set());
    };
    window.addEventListener('urlchange', handleUrlChange);
    return () => window.removeEventListener('urlchange', handleUrlChange);
  }, []);

  if (!Array.isArray(conferencesData)) {
    return <div>Loading conferences...</div>;
  }

  return (
    <AcceptedPapersStatusProvider>
    <div className="min-h-screen bg-neutral-50">
      <Header onSearch={setSearchQuery} showEmptyMessage={false} />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="space-y-3 py-4">
          {/* Category filter buttons */}
          <div className="bg-white shadow-sm rounded-lg p-3 border border-neutral-200">
            <div className="flex flex-wrap gap-1.5">
              {categoryButtons.map(category => (
                <button
                  key={category.id}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    selectedTags.has(category.id)
                      ? 'bg-neutral-800 text-white'
                      : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
                  }`}
                  onClick={() => {
                    const newTags = new Set(selectedTags);
                    if (newTags.has(category.id)) newTags.delete(category.id);
                    else newTags.add(category.id);
                    handleTagsChange(newTags);
                  }}
                >
                  {category.label}
                </button>
              ))}
            </div>
          </div>

          {/* Controls row */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-md border border-neutral-200">
              <label htmlFor="show-past" className="text-xs text-neutral-500">Past</label>
              <Switch id="show-past" checked={showPastConferences} onCheckedChange={setShowPastConferences} />
            </div>

            <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-md border border-neutral-200">
              <label htmlFor="top-tier-only" className="text-xs text-neutral-500 flex items-center gap-1">
                Top tier
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <HelpCircle className="h-3 w-3 text-neutral-300 hover:text-neutral-500 cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs">
                      <p>ERA A-rated conferences from <a href="http://www.conferenceranks.com/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">conferenceranks.com</a></p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </label>
              <Switch id="top-tier-only" checked={showTopTierOnly} onCheckedChange={setShowTopTierOnly} />
            </div>

            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className="h-7 gap-1 text-xs border-neutral-200">
                  <Globe className="h-3.5 w-3.5" />
                  Country
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-64 p-4 bg-white" align="start">
                <div className="mb-3">
                  <h4 className="text-sm font-medium text-gray-800">Country</h4>
                </div>
                <div className="max-h-60 overflow-y-auto space-y-1.5" style={{ WebkitOverflowScrolling: "touch" }}>
                  {getAllCountries(conferencesData as Conference[]).map(country => (
                    <div key={country} className="flex items-center space-x-2 hover:bg-gray-50 p-1 rounded">
                      <Checkbox
                        id={`country-${country}`}
                        checked={selectedCountries.has(country)}
                        onCheckedChange={() => {
                          const newCountries = new Set(selectedCountries);
                          if (newCountries.has(country)) newCountries.delete(country);
                          else newCountries.add(country);
                          handleCountriesChange(newCountries);
                        }}
                      />
                      <label htmlFor={`country-${country}`} className="text-sm text-gray-700 cursor-pointer w-full py-0.5">
                        {country}
                      </label>
                    </div>
                  ))}
                </div>
              </PopoverContent>
            </Popover>

            {Array.from(selectedCountries).map(country => (
              <button
                key={country}
                className="inline-flex items-center px-2.5 py-1 rounded-full text-xs bg-neutral-800 text-white font-medium"
                onClick={() => {
                  const newCountries = new Set(selectedCountries);
                  newCountries.delete(country);
                  handleCountriesChange(newCountries);
                }}
              >
                {country}
                <X className="ml-1 h-3 w-3" />
              </button>
            ))}

            {(selectedTags.size > 0 || selectedCountries.size > 0) && (
              <button
                onClick={() => { handleTagsChange(new Set()); handleCountriesChange(new Set()); }}
                className="text-xs text-neutral-400 hover:text-neutral-600 underline"
              >
                Clear all
              </button>
            )}
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-8">
        {matchedTitles.size === 0 ? (
          <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-md p-4">
            <p className="text-center text-sm">
              No upcoming conferences found — enable "Past" to see previous ones
            </p>
          </div>
        ) : (
          <ConferenceTable
            rows={tableRows}
            yearColumns={yearColumns}
            sortMode={sortMode}
            onSortChange={setSortMode}
          />
        )}
      </main>
    </div>
    </AcceptedPapersStatusProvider>
  );
};

export default Index;
